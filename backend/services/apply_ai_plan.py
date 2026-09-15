"""Apply a grounded AI edit plan as one optimistic ProjectState mutation."""
from __future__ import annotations

import copy
import uuid

from fastapi import HTTPException

from core.security import utc_now
from db.mongo import get_db
from models.project_state import CaptionCue, Clip, ClipTransition, ProjectStateDocument


def _conflict(message: str, current_version: int) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "error": {
                "code": "planner.version_conflict",
                "message": message,
                "current_version": current_version,
            }
        },
    )


def _transition(payload: dict, field: str) -> ClipTransition | None:
    value = payload.get(field)
    return ClipTransition(**value) if value else None


async def apply_plan(
    *,
    plan: dict,
    user_id: str,
    expected_version: int,
    replace_existing_video_clips: bool,
) -> dict:
    db = get_db()
    state = await db.project_states.find_one(
        {"project_id": plan["project_id"], "user_id": user_id},
        {"_id": 0},
    )
    if not state:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "project_state.not_found",
                    "message": "Project state not found",
                }
            },
        )
    if state["version"] != expected_version:
        raise _conflict("Project changed since it was loaded", state["version"])
    if plan["project_state_version"] != expected_version:
        raise _conflict(
            "AI plan was generated for an older ProjectState version",
            state["version"],
        )
    if plan.get("status") != "proposed":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "planner.plan_not_proposed",
                    "message": "Only proposed plans can be applied",
                }
            },
        )

    candidate = copy.deepcopy(state)
    asset_ids = {
        operation["payload"]["asset_id"]
        for operation in plan.get("operations", [])
        if operation.get("operation") in {"add_clip", "add_broll_overlay"}
    }
    assets = {}
    if asset_ids:
        docs = await db.assets.find(
            {
                "id": {"$in": list(asset_ids)},
                "user_id": user_id,
                "processing_status": "ready",
            },
            {"_id": 0, "id": 1, "kind": 1, "duration_sec": 1},
        ).to_list(len(asset_ids))
        assets = {doc["id"]: doc for doc in docs}

    missing = sorted(asset_ids - set(assets))
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "planner.asset_unavailable",
                    "message": "One or more source assets are no longer ready",
                    "asset_ids": missing,
                }
            },
        )

    touched_video_tracks: set[tuple[str, str]] = set()
    for operation in plan.get("operations", []):
        operation_type = operation.get("operation")
        if operation_type not in {"add_clip", "add_broll_overlay", "add_caption"}:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "planner.unsupported_operation",
                        "message": "Plan contains an unsupported operation",
                    }
                },
            )

        payload = operation["payload"]
        sequence = next(
            (
                item
                for item in candidate["sequences"]
                if item["id"] == payload["sequence_id"]
            ),
            None,
        )
        if not sequence:
            raise HTTPException(status_code=422, detail="Plan sequence no longer exists")

        if operation_type == "add_caption":
            cue = CaptionCue(
                id=str(uuid.uuid4()),
                start=int(payload["start"]),
                duration=int(payload["duration"]),
                text=str(payload["text"]),
                style={
                    **payload.get("style", {}),
                    "ai_plan_id": plan["id"],
                },
            )
            sequence.setdefault("captions", []).append(cue.model_dump(mode="json"))
            continue

        track = next(
            (
                item
                for item in sequence["tracks"]
                if item["id"] == payload["track_id"]
            ),
            None,
        )
        expected_kind = "overlay" if operation_type == "add_broll_overlay" else "video"
        if not track or track["kind"] != expected_kind:
            raise HTTPException(
                status_code=422,
                detail=f"Plan target {expected_kind} track no longer exists",
            )
        if track.get("locked"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "edit.track_locked",
                        "message": f"Target {expected_kind} track is locked",
                    }
                },
            )

        key = (sequence["id"], track["id"])
        if operation_type == "add_clip" and key not in touched_video_tracks:
            if track["clips"] and not replace_existing_video_clips:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "planner.nonempty_timeline",
                            "message": (
                                "Target video track already has clips; "
                                "explicitly allow replacement"
                            ),
                        }
                    },
                )
            if replace_existing_video_clips:
                track["clips"] = []
                sequence["captions"] = [
                    cue
                    for cue in sequence.get("captions", [])
                    if not cue.get("style", {}).get("ai_plan_id")
                ]
                for overlay in sequence.get("tracks", []):
                    if overlay.get("kind") == "overlay":
                        overlay["clips"] = [
                            clip
                            for clip in overlay.get("clips", [])
                            if not clip.get("metadata", {}).get("ai_plan_id")
                        ]
            touched_video_tracks.add(key)

        asset = assets[payload["asset_id"]]
        if asset["kind"] not in {"video", "image"}:
            raise HTTPException(status_code=422, detail="Plan source is not a visual asset")

        source_start = int(payload.get("source_start", 0))
        source_duration = int(payload["source_duration"])
        asset_duration_sec = float(asset.get("duration_sec") or 0.0)
        if asset_duration_sec > 0:
            ticks_per_second = (
                sequence["timebase"]["numerator"]
                / sequence["timebase"]["denominator"]
            )
            asset_duration_ticks = round(asset_duration_sec * ticks_per_second)
            if source_start + source_duration > asset_duration_ticks + 1:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "planner.source_out_of_bounds",
                            "message": "Planned source range exceeds the media duration",
                            "asset_id": payload["asset_id"],
                        }
                    },
                )

        clip = Clip(
            id=str(uuid.uuid4()),
            asset_id=payload["asset_id"],
            timeline_start=int(payload["timeline_start"]),
            duration=int(payload["duration"]),
            source_start=source_start,
            source_duration=source_duration,
            volume=float(payload.get("volume", 1.0)),
            transition_in=_transition(payload, "transition_in"),
            transition_out=_transition(payload, "transition_out"),
            metadata={
                **payload.get("metadata", {}),
                "ai_plan_id": plan["id"],
            },
        )
        track["clips"].append(clip.model_dump(mode="json"))

    now = utc_now()
    candidate["version"] = state["version"] + 1
    candidate["updated_at"] = now
    candidate = ProjectStateDocument(**candidate).model_dump()
    result = await db.project_states.replace_one(
        {
            "project_id": plan["project_id"],
            "user_id": user_id,
            "version": expected_version,
        },
        candidate,
    )
    if result.modified_count != 1:
        latest = await db.project_states.find_one(
            {"project_id": plan["project_id"], "user_id": user_id},
            {"_id": 0, "version": 1},
        )
        raise _conflict(
            "Project changed while the plan was being applied",
            (latest or {}).get("version", expected_version),
        )

    await db.edit_operations.insert_one(
        {
            "id": str(uuid.uuid4()),
            "project_id": plan["project_id"],
            "user_id": user_id,
            "from_version": expected_version,
            "to_version": candidate["version"],
            "operation": "apply_ai_plan",
            "payload": {
                "ai_plan_id": plan["id"],
                "operation_count": len(plan.get("operations", [])),
                "replace_existing_video_clips": replace_existing_video_clips,
            },
            "created_at": now,
        }
    )
    await db.project_state_versions.insert_one(
        {
            **copy.deepcopy(candidate),
            "snapshot_created_at": now,
            "operation": f"apply_ai_plan:{plan['id']}",
        }
    )
    await db.ai_edit_plans.update_one(
        {"id": plan["id"], "user_id": user_id, "status": "proposed"},
        {
            "$set": {
                "status": "applied",
                "applied_project_state_version": candidate["version"],
                "updated_at": now,
            }
        },
    )
    return candidate
