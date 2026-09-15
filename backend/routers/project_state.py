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
    CaptionCue,
    Clip,
    ClipTransform,
    ClipTransition,
    EditOperation,
    ProjectStateDocument,
    ProjectStateOut,
    ProjectStateReplace,
    ProjectVersionSummary,
    RestoreVersionRequest,
    Sequence,
    Track,
    TrackKind,
)

router = APIRouter(prefix="/projects", tags=["project-state"])


def _error(code: str, message: str, http_status: int = 422) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"error": {"code": code, "message": message}},
    )


def _not_found() -> HTTPException:
    return _error("resource.not_found", "Project not found", 404)


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
    project = await get_db().projects.find_one(
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
            Track(id=str(uuid.uuid4()), kind=TrackKind.overlay, name="Overlays"),
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
        await _save_snapshot(state, operation="backfill")
        return state

    state = _new_state(project_id, user_id)
    try:
        await db.project_states.insert_one(copy.deepcopy(state))
        await _save_snapshot(state, operation="initialize")
    except Exception:
        existing = await db.project_states.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0}
        )
        if existing:
            return existing
        raise
    return state


async def _save_snapshot(state: dict, operation: str | None = None) -> None:
    """Persist a complete immutable version snapshot for undo/restore."""
    await get_db().project_state_versions.update_one(
        {
            "project_id": state["project_id"],
            "user_id": state["user_id"],
            "version": state["version"],
        },
        {
            "$setOnInsert": {
                **copy.deepcopy(state),
                "snapshot_created_at": utc_now(),
                "operation": operation,
            }
        },
        upsert=True,
    )


def _find_sequence(state: dict, sequence_id: str) -> dict:
    sequence = next((s for s in state["sequences"] if s["id"] == sequence_id), None)
    if not sequence:
        raise _error("edit.sequence_not_found", "Sequence not found")
    return sequence


def _find_track(sequence: dict, track_id: str) -> dict:
    track = next((t for t in sequence["tracks"] if t["id"] == track_id), None)
    if not track:
        raise _error("edit.track_not_found", "Track not found")
    return track


def _find_clip(track: dict, clip_id: str) -> dict:
    clip = next((c for c in track["clips"] if c["id"] == clip_id), None)
    if not clip:
        raise _error("edit.clip_not_found", "Clip not found")
    return clip


def _require_unlocked(track: dict) -> None:
    if track.get("locked"):
        raise _error("edit.track_locked", "Track is locked", 409)


async def _validate_add_clip_asset(
    *, state: dict, payload: dict, user_id: str
) -> None:
    sequence = _find_sequence(state, str(payload.get("sequence_id", "")))
    track = _find_track(sequence, str(payload.get("track_id", "")))
    _require_unlocked(track)

    asset_id = str(payload.get("asset_id", ""))
    asset = await get_db().assets.find_one(
        {"id": asset_id, "user_id": user_id}, {"_id": 0}
    )
    if not asset:
        raise _error("edit.asset_not_found", "Asset not found", 404)
    if asset.get("processing_status") != "ready":
        raise _error("edit.asset_not_ready", "Asset is still processing", 409)

    allowed = {
        "video": {"video", "image"},
        "overlay": {"video", "image"},
        "audio": {"audio", "video"},
        "caption": set(),
    }
    if asset["kind"] not in allowed.get(track["kind"], set()):
        raise _error(
            "edit.asset_track_mismatch",
            f"{asset['kind']} asset cannot be added to {track['kind']} track",
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
            raise _error("edit.invalid_name", "Sequence name must be 1-120 characters")
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
            raise _error("edit.invalid_track", str(exc)) from exc
        sequence["tracks"].append(track.model_dump(mode="json"))

    elif op == "remove_track":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track_id = str(p.get("track_id", ""))
        track = _find_track(sequence, track_id)
        _require_unlocked(track)
        sequence["tracks"] = [t for t in sequence["tracks"] if t["id"] != track_id]

    elif op == "add_clip":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        _require_unlocked(track)
        try:
            clip = Clip(
                id=str(p.get("clip_id") or uuid.uuid4()),
                asset_id=str(p["asset_id"]),
                timeline_start=int(p.get("timeline_start", 0)),
                duration=int(p["duration"]),
                source_start=int(p.get("source_start", 0)),
                source_duration=int(p.get("source_duration", p["duration"])),
                volume=float(p.get("volume", 1.0)),
                playback_rate=float(p.get("playback_rate", 1.0)),
                transform=ClipTransform(**p.get("transform", {})),
                transition_in=(
                    ClipTransition(**p["transition_in"])
                    if p.get("transition_in")
                    else None
                ),
                transition_out=(
                    ClipTransition(**p["transition_out"])
                    if p.get("transition_out")
                    else None
                ),
                metadata=p.get("metadata", {}),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise _error("edit.invalid_clip", str(exc)) from exc
        track["clips"].append(clip.model_dump(mode="json"))

    elif op in {"remove_clip", "ripple_delete"}:
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        _require_unlocked(track)
        clip = _find_clip(track, str(p.get("clip_id", "")))
        removed_start = clip["timeline_start"]
        removed_duration = clip["duration"]
        removed_end = removed_start + removed_duration
        track["clips"] = [c for c in track["clips"] if c["id"] != clip["id"]]
        if op == "ripple_delete":
            for item in track["clips"]:
                if item["timeline_start"] >= removed_end:
                    item["timeline_start"] -= removed_duration

    elif op == "duplicate_clip":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        _require_unlocked(track)
        source = _find_clip(track, str(p.get("clip_id", "")))
        duplicate = copy.deepcopy(source)
        duplicate["id"] = str(p.get("new_clip_id") or uuid.uuid4())
        duplicate["timeline_start"] = int(
            p.get("timeline_start", source["timeline_start"] + source["duration"])
        )
        track["clips"].append(duplicate)

    elif op == "split_clip":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        _require_unlocked(track)
        clip = _find_clip(track, str(p.get("clip_id", "")))
        split_at = int(p.get("split_at", -1))
        start = clip["timeline_start"]
        end = start + clip["duration"]
        if split_at <= start or split_at >= end:
            raise _error("edit.invalid_split", "split_at must be inside the clip")
        if clip["source_duration"] < 2:
            raise _error("edit.invalid_split", "source range is too short to split")

        left_duration = split_at - start
        right_duration = clip["duration"] - left_duration
        left_source_duration = max(
            1, round(clip["source_duration"] * left_duration / clip["duration"])
        )
        if left_source_duration >= clip["source_duration"]:
            left_source_duration = clip["source_duration"] - 1
        right_source_duration = clip["source_duration"] - left_source_duration

        original_transition_out = copy.deepcopy(
            clip.get("transition_out")
        )
        clip["duration"] = left_duration
        clip["source_duration"] = left_source_duration
        clip["transition_out"] = None
        right = copy.deepcopy(clip)
        right["id"] = str(p.get("new_clip_id") or uuid.uuid4())
        right["timeline_start"] = split_at
        right["duration"] = right_duration
        right["source_start"] = clip["source_start"] + left_source_duration
        right["source_duration"] = right_source_duration
        right["transition_in"] = None
        right["transition_out"] = original_transition_out
        track["clips"].append(right)

    elif op in {"move_clip", "trim_clip", "set_clip_properties"}:
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        _require_unlocked(track)
        clip = _find_clip(track, str(p.get("clip_id", "")))

        if op == "move_clip":
            timeline_start = int(p.get("timeline_start", -1))
            if timeline_start < 0:
                raise _error("edit.invalid_time", "timeline_start must be >= 0")
            clip["timeline_start"] = timeline_start

        elif op == "trim_clip":
            for field in ("source_start", "source_duration", "duration"):
                if field in p:
                    clip[field] = int(p[field])

        else:
            for field in ("enabled", "volume", "playback_rate"):
                if field in p:
                    clip[field] = p[field]
            if "transform" in p:
                merged = {**clip.get("transform", {}), **p["transform"]}
                clip["transform"] = ClipTransform(**merged).model_dump(mode="json")
            for field in ("transition_in", "transition_out"):
                if field in p:
                    value = p[field]
                    clip[field] = (
                        ClipTransition(**value).model_dump(mode="json")
                        if value
                        else None
                    )
            if "metadata" in p:
                clip["metadata"] = {**clip.get("metadata", {}), **p["metadata"]}

        try:
            Clip(**clip)
        except ValidationError as exc:
            raise _error("edit.invalid_clip", str(exc)) from exc

    elif op in {"add_caption", "update_caption", "remove_caption"}:
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        if op == "add_caption":
            try:
                cue = CaptionCue(
                    id=str(p.get("caption_id") or uuid.uuid4()),
                    start=int(p["start"]),
                    duration=int(p["duration"]),
                    text=str(p["text"]),
                    style=p.get("style", {}),
                )
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                raise _error("edit.invalid_caption", str(exc)) from exc
            sequence["captions"].append(cue.model_dump(mode="json"))

        else:
            caption_id = str(p.get("caption_id", ""))
            cue = next(
                (item for item in sequence.get("captions", []) if item["id"] == caption_id),
                None,
            )
            if not cue:
                raise _error("edit.caption_not_found", "Caption not found")
            if op == "remove_caption":
                sequence["captions"] = [
                    item for item in sequence["captions"] if item["id"] != caption_id
                ]
            else:
                for field in ("start", "duration", "text"):
                    if field in p:
                        cue[field] = p[field]
                if "style" in p:
                    cue["style"] = {**cue.get("style", {}), **p["style"]}
                try:
                    CaptionCue(**cue)
                except ValidationError as exc:
                    raise _error("edit.invalid_caption", str(exc)) from exc

    elif op == "set_track_properties":
        sequence = _find_sequence(next_state, str(p.get("sequence_id", "")))
        track = _find_track(sequence, str(p.get("track_id", "")))
        if "name" in p:
            name = str(p["name"]).strip()
            if not name or len(name) > 120:
                raise _error("edit.invalid_name", "Track name must be 1-120 characters")
            track["name"] = name
        if "muted" in p:
            track["muted"] = bool(p["muted"])
        if "locked" in p:
            track["locked"] = bool(p["locked"])

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
    await _save_snapshot(candidate, operation="replace_state")
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

    if body.operation == "add_clip":
        await _validate_add_clip_asset(
            state=current, payload=body.payload, user_id=user["id"]
        )

    candidate = _apply_operation(current, body)
    now = utc_now()
    candidate["version"] = current["version"] + 1
    candidate["updated_at"] = now
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
    await _save_snapshot(candidate, operation=body.operation)
    return ProjectStateOut(**candidate)


@router.get("/{project_id}/versions", response_model=list[ProjectVersionSummary])
async def list_project_versions(
    project_id: str,
    limit: int = 50,
    user: dict = Depends(get_current_user),
) -> list[ProjectVersionSummary]:
    await _owned_project(project_id, user["id"])
    docs = await (
        get_db().project_state_versions.find(
            {"project_id": project_id, "user_id": user["id"]},
            {"_id": 0, "version": 1, "snapshot_created_at": 1, "operation": 1},
        )
        .sort("version", -1)
        .limit(max(1, min(limit, 200)))
        .to_list(max(1, min(limit, 200)))
    )
    return [
        ProjectVersionSummary(
            version=doc["version"],
            created_at=doc.get("snapshot_created_at"),
            operation=doc.get("operation"),
        )
        for doc in docs
    ]


@router.get("/{project_id}/versions/{version}", response_model=ProjectStateOut)
async def get_project_version(
    project_id: str,
    version: int,
    user: dict = Depends(get_current_user),
) -> ProjectStateOut:
    await _owned_project(project_id, user["id"])
    snapshot = await get_db().project_state_versions.find_one(
        {"project_id": project_id, "user_id": user["id"], "version": version},
        {"_id": 0, "snapshot_created_at": 0, "operation": 0},
    )
    if not snapshot:
        raise _error("project_state.version_not_found", "Version not found", 404)
    return ProjectStateOut(**snapshot)


@router.post("/{project_id}/versions/{version}/restore", response_model=ProjectStateOut)
async def restore_project_version(
    project_id: str,
    version: int,
    body: RestoreVersionRequest,
    user: dict = Depends(get_current_user),
) -> ProjectStateOut:
    db = get_db()
    current = await _get_or_create_state(project_id, user["id"])
    if current["version"] != body.expected_version:
        raise _conflict(current["version"])

    snapshot = await db.project_state_versions.find_one(
        {"project_id": project_id, "user_id": user["id"], "version": version},
        {"_id": 0, "snapshot_created_at": 0, "operation": 0},
    )
    if not snapshot:
        raise _error("project_state.version_not_found", "Version not found", 404)

    now = utc_now()
    restored = {
        **snapshot,
        "version": current["version"] + 1,
        "created_at": current["created_at"],
        "updated_at": now,
    }
    restored = ProjectStateDocument(**restored).model_dump()

    result = await db.project_states.replace_one(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "version": body.expected_version,
        },
        restored,
    )
    if result.modified_count != 1:
        latest = await db.project_states.find_one(
            {"project_id": project_id, "user_id": user["id"]},
            {"_id": 0, "version": 1},
        )
        raise _conflict((latest or {}).get("version", body.expected_version))

    await db.edit_operations.insert_one(
        {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "user_id": user["id"],
            "from_version": body.expected_version,
            "to_version": restored["version"],
            "operation": "restore_version",
            "payload": {"restored_from_version": version},
            "created_at": now,
        }
    )
    await _save_snapshot(restored, operation=f"restore:{version}")
    return ProjectStateOut(**restored)
