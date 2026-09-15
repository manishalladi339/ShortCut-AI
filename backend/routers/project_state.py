"""Canonical ProjectState API with optimistic concurrency and deterministic operations."""
from __future__ import annotations

import copy
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.project_state import (
    Clip,
    EditOperation,
    ProjectStateDocument,
    ProjectStateOut,
    ProjectStateReplace,
    Sequence,
    Track,
    TrackKind,
)

router = APIRouter(prefix="/projects", tags=["project-state"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
    )


def _conflict(current_version: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": {
                "code": "project_state.version_conflict",
                "message": "Project state changed since it was loaded",
                "current_version": current_version,
            }
        },
    )


async def _owned_project(project_id: str, user_id: str) -> dict:
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id, "user_id": user_id}, {"_id": 0, "id": 1}
    )
    if not project:
        raise _not_found()
    return project


def _new_state(project_id: str, user_id: str) -> dict:
    now = utc_now()
    sequence_id = str(uuid.uuid4())
    sequence = Sequence(
        id=sequence_id,
        name="Main",
        tracks=[
            Track(id=str(uuid.uuid4()), kind=TrackKind.video, name="Video 1"),
            Track(id=str(uuid.uuid4()), kind=TrackKind.audio, name="Audio 1"),
            Track(id=str(uuid.uuid4()), kind=TrackKind.caption, name="Captions"),
        ],
    )
    return ProjectStateDocument(
        project_id=project_id,
        user_id=user_id,
        version=1,
        active_sequence_id=sequence_id,
        sequences=[sequence],
        created_at=now,
        updated_at=now,
    ).model_dump()


async def _get_or_create_state(project_id: str, user_id: str) -> dict:
    db = get_db()
    await _owned_project(project_id, user_id)
    state = await db.project_states.find_one(
        {"project_id": project_id, "user_id": user_id}, {"_id": 0}
    )
    if state:
        return state

    state = _new_state(project_id, user_id)
    try:
        await db.project_states.insert_one(copy.deepcopy(state))
    except Exception:
        # Another request may have initialized the state concurrently.
        existing = await db.project_states.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0}
        )
        if existing:
            return existing
        raise
    return state


def _find_sequence(state: dict, sequence_id: str) -> dict:
    for sequence in state["sequences"]:
        if sequence["id"] == sequence_id:
            return sequence
    raise HTTPException(
        status_code=422,
        detail={"error": {"code": "edit.sequence_not_found", "message": "Sequence not found"}},
    )


def _find_track(sequence: dict, track_id: str) -> dict:
    for track in sequence["tracks"]:
        if track["id"] == track_id:
            return track
    raise HTTPException(
        status_code=422,
        detail={"error": {"code": "edit.track_not_found", "message": "Track not found"}},
    )


def _apply_operation(state: dict, edit: EditOperation) -> dict:
    next_state = copy.deepcopy(state)
    op = edit.operation
    p = edit.payload

    if op == "set_active_sequence":
        sequence_id = str(p.get("sequence_id", ""))
        _find_sequence(next_state, sequence_id)
        next_state["active_sequence_id"] = sequence_id

    elif op == "rename_sequence":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        name = str(p.get("name", "")).strip()
        if not name or len(name) > 120:
            raise HTTPException(status_code=422, detail={"error": {"code": "edit.invalid_name", "message": "Sequence name must be 1-120 characters"}})
        sequence["name"] = name

    elif op == "add_track":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        try:
            track = Track(
                id=str(p.get("track_id") or uuid.uuid4()),
                kind=TrackKind(str(p["kind"])),
                name=str(p.get("name") or "Track"),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail={"error": {"code": "edit.invalid_track", "message": str(exc)}}) from exc
        sequence["tracks"].append(track.model_dump(mode="json"))

    elif op == "remove_clip":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        clip_id = str(p.get("clip_id", ""))
        before = len(track["clips"])
        track["clips"] = [clip for clip in track["clips"] if clip["id"] != clip_id]
        if len(track["clips"]) == before:
            raise HTTPException(status_code=422, detail={"error": {"code": "edit.clip_not_found", "message": "Clip not found"}})

    elif op in {"move_clip", "trim_clip"}:
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        clip_id = str(p.get("clip_id", ""))
        clip = next((item for item in track["clips"] if item["id"] == clip_id), None)
        if not clip:
            raise HTTPException(status_code=422, detail={"error": {"code": "edit.clip_not_found", "message": "Clip not found"}})

        if op == "move_clip":
            timeline_start = int(p.get("timeline_start", -1))
            if timeline_start < 0:
                raise HTTPException(status_code=422, detail={"error": {"code": "edit.invalid_time", "message": "timeline_start must be >= 0"}})
            clip["timeline_start"] = timeline_start
        else:
            for field in ("source_start", "source_duration", "duration"):
                if field in p:
                    clip[field] = int(p[field])
            try:
                Clip(**clip)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail={"error": {"code": "edit.invalid_trim", "message": str(exc)}}) from exc

    # Revalidate the entire document before persistence.
    validated = ProjectStateDocument(**next_state)
    return validated.model_dump()


@router.get("/{project_id}/state", response_model=ProjectStateOut)
async def get_project_state(
    project_id: str, user: dict = Depends(get_current_user)
) -> ProjectStateOut:
    state = await _get_or_create_state(project_id, user["id"])
    return ProjectStateOut(**state)


@router.put("/{project_id}/state", response_model=ProjectStateOut)
async def replace_project_state(
    project_id: str,
    body: ProjectStateReplace,
    user: dict = Depends(get_current_user),
) -> ProjectStateOut:
    db = get_db()
    current = await _get_or_create_state(project_id, user["id"])
    if current["version"] != body.expected_version:
        raise _conflict(current["version"])

    now = utc_now()
    candidate = ProjectStateDocument(
        project_id=project_id,
        user_id=user["id"],
        version=current["version"] + 1,
        active_sequence_id=body.active_sequence_id,
        sequences=body.sequences,
        created_at=current["created_at"],
        updated_at=now,
    ).model_dump()

    result = await db.project_states.replace_one(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "version": body.expected_version,
        },
        candidate,
    )
    if result.modified_count != 1:
        latest = await db.project_states.find_one(
            {"project_id": project_id, "user_id": user["id"]}, {"_id": 0, "version": 1}
        )
        raise _conflict((latest or {}).get("version", body.expected_version))

    await db.edit_operations.insert_one(
        {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "user_id": user["id"],
            "from_version": body.expected_version,
            "to_version": candidate["version"],
            "operation": "replace_state",
            "payload": {},
            "created_at": now,
        }
    )
    return ProjectStateOut(**candidate)


@router.post("/{project_id}/operations", response_model=ProjectStateOut)
async def apply_edit_operation(
    project_id: str,
    body: EditOperation,
    user: dict = Depends(get_current_user),
) -> ProjectStateOut:
    db = get_db()
    current = await _get_or_create_state(project_id, user["id"])
    if current["version"] != body.expected_version:
        raise _conflict(current["version"])

    candidate = _apply_operation(current, body)
    now = utc_now()
    candidate["version"] = current["version"] + 1
    candidate["updated_at"] = now

    # Validate once more after version/timestamp changes.
    candidate = ProjectStateDocument(**candidate).model_dump()

    result = await db.project_states.replace_one(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "version": body.expected_version,
        },
        candidate,
    )
    if result.modified_count != 1:
        latest = await db.project_states.find_one(
            {"project_id": project_id, "user_id": user["id"]}, {"_id": 0, "version": 1}
        )
        raise _conflict((latest or {}).get("version", body.expected_version))

    await db.edit_operations.insert_one(
        {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "user_id": user["id"],
            "from_version": body.expected_version,
            "to_version": candidate["version"],
            "operation": body.operation,
            "payload": body.payload,
            "created_at": now,
        }
    )
    return ProjectStateOut(**candidate)
