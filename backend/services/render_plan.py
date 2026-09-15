"""Compile ProjectState into a deterministic render plan."""
from __future__ import annotations

from fastapi import HTTPException

from db.mongo import get_db
from models.render_plan import RenderCaption, RenderClip, RenderPlan


async def compile_render_plan(
    *, project_id: str, user_id: str, sequence_id: str | None = None
) -> RenderPlan:
    db = get_db()
    state = await db.project_states.find_one(
        {"project_id": project_id, "user_id": user_id}, {"_id": 0}
    )
    if not state:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "project_state.not_found", "message": "Project state not found"}},
        )

    target_id = sequence_id or state["active_sequence_id"]
    sequence = next((s for s in state["sequences"] if s["id"] == target_id), None)
    if not sequence:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "sequence.not_found", "message": "Sequence not found"}},
        )

    asset_ids = {
        clip["asset_id"]
        for track in sequence["tracks"]
        for clip in track["clips"]
        if clip.get("enabled", True)
    }
    assets = {}
    if asset_ids:
        docs = await db.assets.find(
            {"id": {"$in": list(asset_ids)}, "user_id": user_id},
            {"_id": 0},
        ).to_list(len(asset_ids))
        assets = {doc["id"]: doc for doc in docs}

    missing = sorted(asset_ids - set(assets))
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "render.asset_missing",
                    "message": "One or more timeline assets are unavailable",
                    "asset_ids": missing,
                }
            },
        )

    render_clips: list[RenderClip] = []
    duration_ticks = 0
    for track_index, track in enumerate(sequence["tracks"]):
        if track.get("muted"):
            continue
        for clip in track["clips"]:
            if not clip.get("enabled", True):
                continue
            asset = assets[clip["asset_id"]]
            if asset.get("processing_status") != "ready":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "render.asset_not_ready",
                            "message": f"Asset {asset['id']} has not finished processing",
                        }
                    },
                )
            metadata = {
                **clip.get("metadata", {}),
                "_asset_kind": asset.get("kind"),
                "_asset_audio_codec": asset.get("media_metadata", {}).get("audio_codec"),
                "_transform": clip.get("transform", {}),
            }
            render_clip = RenderClip(
                clip_id=clip["id"],
                track_id=track["id"],
                track_kind=track["kind"],
                track_index=track_index,
                asset_id=clip["asset_id"],
                source_storage_key=asset["storage_key"],
                timeline_start=clip["timeline_start"],
                duration=clip["duration"],
                source_start=clip["source_start"],
                source_duration=clip["source_duration"],
                loop_source=bool(clip.get("loop_source", False)),
                playback_rate=clip["playback_rate"],
                volume=clip["volume"],
                transition_in=clip.get("transition_in"),
                transition_out=clip.get("transition_out"),
                ducking=clip.get("ducking"),
                metadata=metadata,
            )
            render_clips.append(render_clip)
            duration_ticks = max(duration_ticks, clip["timeline_start"] + clip["duration"])

    render_clips.sort(key=lambda c: (c.track_index, c.timeline_start, c.clip_id))
    render_captions = [
        RenderCaption(**cue)
        for cue in sorted(sequence.get("captions", []), key=lambda item: item["start"])
    ]
    for cue in render_captions:
        duration_ticks = max(duration_ticks, cue.start + cue.duration)

    return RenderPlan(
        project_id=project_id,
        project_state_version=state["version"],
        sequence_id=sequence["id"],
        width=sequence["width"],
        height=sequence["height"],
        timebase_numerator=sequence["timebase"]["numerator"],
        timebase_denominator=sequence["timebase"]["denominator"],
        duration_ticks=duration_ticks,
        clips=render_clips,
        captions=render_captions,
    )
