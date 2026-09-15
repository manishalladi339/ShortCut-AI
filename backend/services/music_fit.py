"""Music-bed fit policies applied after the core story plan is built."""
from __future__ import annotations

from fastapi import HTTPException

from db.mongo import get_db
from models.ai_plan import CreateAIEditPlanRequest
from services.plan_review import assign_operation_ids
from services.transition_planning import bounded_fade_ticks


def _planned_output_duration_ticks(plan: dict) -> int:
    ends = [
        int((operation.get("payload") or {}).get("timeline_start") or 0)
        + int((operation.get("payload") or {}).get("duration") or 0)
        for operation in plan.get("operations") or []
        if operation.get("operation") == "add_clip"
    ]
    return max(ends, default=0)


async def attach_looping_music_bed(
    *,
    plan: dict,
    state: dict,
    user_id: str,
    body: CreateAIEditPlanRequest,
) -> dict:
    """Attach one user-selected music bed that may repeat to fit output.

    This path is used only for explicit `music_fit_mode="loop"`. It keeps loop
    intent canonical in the proposed operation instead of silently repeating an
    input inside the renderer.
    """
    if not body.music_asset_id:
        return plan

    sequence = next(
        (
            item
            for item in state.get("sequences") or []
            if item.get("id") == state.get("active_sequence_id")
        ),
        None,
    )
    if not sequence:
        raise HTTPException(status_code=409, detail="Active sequence is unavailable")

    audio_track = next(
        (
            track
            for track in sequence.get("tracks") or []
            if track.get("kind") == "audio" and not track.get("locked")
        ),
        None,
    )
    if not audio_track:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "planner.audio_track_unavailable",
                    "message": "An unlocked audio track is required for a music bed",
                }
            },
        )

    asset = await get_db().assets.find_one(
        {
            "id": body.music_asset_id,
            "user_id": user_id,
            "processing_status": "ready",
        },
        {"_id": 0, "id": 1, "kind": 1, "duration_sec": 1},
    )
    if not asset:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "planner.music_asset_unavailable",
                    "message": "Selected music asset is not available or ready",
                }
            },
        )
    if asset.get("kind") != "audio":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "planner.music_asset_not_audio",
                    "message": "Selected music asset must be an audio asset",
                }
            },
        )

    ticks_per_second = (
        sequence["timebase"]["numerator"]
        / sequence["timebase"]["denominator"]
    )
    output_duration = _planned_output_duration_ticks(plan)
    if output_duration <= 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "planner.music_output_unavailable",
                    "message": "Music cannot be fitted before the primary output duration is known",
                }
            },
        )

    asset_duration_ticks = round(float(asset.get("duration_sec") or 0.0) * ticks_per_second)
    source_start = round(body.music_source_start_sec * ticks_per_second)
    if asset_duration_ticks <= 0 or source_start >= asset_duration_ticks:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "planner.music_source_out_of_bounds",
                    "message": "Music source start must be inside the selected audio asset",
                }
            },
        )

    available_source_ticks = asset_duration_ticks - source_start
    loop_source = output_duration > available_source_ticks
    fade_ticks, fade_metadata = bounded_fade_ticks(
        clip_duration_ticks=output_duration,
        ticks_per_second=ticks_per_second,
        requested_fade_sec=body.music_fade_sec,
        clip_fraction_cap=0.25,
    )
    transition = (
        {"kind": "fade", "duration": fade_ticks}
        if fade_ticks > 0
        else None
    )

    plan.setdefault("operations", []).append(
        {
            "operation": "add_music_bed",
            "payload": {
                "sequence_id": sequence["id"],
                "track_id": audio_track["id"],
                "asset_id": asset["id"],
                "timeline_start": 0,
                "duration": output_duration,
                "source_start": source_start,
                "source_duration": output_duration,
                "loop_source": loop_source,
                "volume": body.music_volume,
                "transition_in": transition,
                "transition_out": transition,
                "metadata": {
                    "ai_plan": True,
                    "music_bed": True,
                    "user_selected_music": True,
                    "music_volume": body.music_volume,
                    "music_source_start_sec": body.music_source_start_sec,
                    "music_fit_mode": "loop",
                    "music_loop_source": loop_source,
                    "music_available_source_ticks": available_source_ticks,
                    "music_output_duration_ticks": output_duration,
                    "music_fade": fade_metadata,
                },
            },
            "reason": (
                "User-selected music bed fitted to the complete planned output "
                + (
                    "by deterministic source repetition"
                    if loop_source
                    else "without repetition because the source is long enough"
                )
            ),
        }
    )
    assign_operation_ids(plan["operations"])
    return plan
