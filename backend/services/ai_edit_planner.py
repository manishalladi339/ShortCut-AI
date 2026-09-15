"""Grounded Create-For-Me edit proposal builder."""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from core.config import settings
from core.security import utc_now
from db.mongo import get_db
from models.ai_plan import CreateAIEditPlanRequest
from services.broll_planning import (
    bounded_broll_source_range,
    build_visual_candidates,
    recommend_broll_for_highlight,
)
from services.conversation_pacing import rebalance_speaker_runs
from services.dead_air import compact_source_ranges
from services.embeddings import get_embedding_provider
from services.highlight_scoring import (
    combine_scores,
    heuristic_highlight_score,
    select_non_overlapping,
)
from services.music_fit import MusicFitError, attach_loop_transitions, plan_loop_segments
from services.narrative_planning import structure_narrative
from services.planner_evaluation import evaluate_plan
from services.plan_review import assign_operation_ids
from services.rhythm_editing import map_rhythm_to_timeline, snap_forward_to_rhythm
from services.semantic_search import cosine_similarity
from services.silence_editing import snap_outward_to_silence
from services.speaker_editing import (
    normalize_speakers,
    primary_speaker,
    speaker_allowed,
)
from services.transition_planning import broll_fade_ticks, bounded_fade_ticks


def _candidate_key(item: dict) -> str:
    return f"{item['asset_id']}:{item['unit_index']}"


def _nearest_visual(record: dict, start: float, end: float) -> dict | None:
    observations = record.get("visual_observations") or []
    if not observations:
        return None
    midpoint = start + (end - start) / 2.0
    nearby = min(
        observations,
        key=lambda item: abs(float(item.get("time") or 0.0) - midpoint),
    )
    return (
        nearby
        if abs(float(nearby.get("time") or 0.0) - midpoint) <= 12.0
        else None
    )


async def build_plan(
    *,
    project: dict,
    user_id: str,
    state: dict,
    body: CreateAIEditPlanRequest,
) -> dict:
    db = get_db()
    records = await db.media_intelligence.find(
        {
            "project_id": project["id"],
            "user_id": user_id,
            "status": "completed",
            "embedding_model": settings.EMBEDDING_MODEL,
        },
        {"_id": 0},
    ).to_list(500)
    if not records:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "planner.no_intelligence",
                    "message": (
                        "Analyze at least one project media asset before "
                        "creating an AI edit plan"
                    ),
                }
            },
        )

    objective = (
        (body.objective or "").strip()
        or (project.get("prompt") or "").strip()
        or (project.get("description") or "").strip()
        or f"Create a strong {project.get('content_type', 'short-form')} edit"
    )
    query_vector = (await get_embedding_provider().embed([objective]))[0]

    asset_ids = [record["asset_id"] for record in records]
    asset_docs = await db.assets.find(
        {"id": {"$in": asset_ids}, "user_id": user_id},
        {"_id": 0, "id": 1, "duration_sec": 1, "kind": 1},
    ).to_list(len(asset_ids))
    assets = {asset["id"]: asset for asset in asset_docs}
    records_by_id = {record["id"]: record for record in records}
    visual_candidates = [
        candidate
        for record in records
        for candidate in build_visual_candidates(record)
    ]

    candidates: list[dict] = []
    for record in records:
        units = record.get("semantic_units") or []
        vectors = record.get("semantic_vectors") or []
        asset = assets.get(record["asset_id"])
        if not asset or asset.get("kind") != "video":
            continue

        silences = record.get("silences") or []
        for index, unit in enumerate(units):
            if index >= len(vectors):
                continue

            speakers = normalize_speakers(unit)
            if not speaker_allowed(
                speakers,
                include=body.include_speakers,
                exclude=body.exclude_speakers,
            ):
                continue

            refined_start, refined_end, silence_reasons = snap_outward_to_silence(
                start=float(unit["start"]),
                end=float(unit["end"]),
                silences=silences,
                snap_window_sec=settings.SILENCE_SNAP_WINDOW_SEC,
            )
            refined_unit = {
                **unit,
                "start": refined_start,
                "end": refined_end,
            }
            heuristic, reasons = heuristic_highlight_score(
                refined_unit,
                asset_duration_sec=asset.get("duration_sec"),
            )
            reasons.extend(silence_reasons)
            if speakers:
                reasons.append("speaker-aware diarization context")

            relevance = cosine_similarity(query_vector, vectors[index])
            visual = _nearest_visual(record, refined_start, refined_end)
            visual_bonus = 0.0
            if visual:
                if visual.get("description"):
                    visual_bonus += 0.025
                    reasons.append("nearby visual context available")
                if visual.get("text_on_screen"):
                    visual_bonus += 0.015
                    reasons.append("nearby on-screen text")

            final = min(
                1.0,
                combine_scores(heuristic, relevance) + visual_bonus,
            )
            candidates.append(
                {
                    "asset_id": record["asset_id"],
                    "intelligence_id": record["id"],
                    "unit_index": index,
                    "start": refined_start,
                    "end": refined_end,
                    "text": unit["text"],
                    "heuristic_score": heuristic,
                    "relevance_score": relevance,
                    "final_score": final,
                    "reasons": reasons + ["semantic relevance to objective"],
                    "narrative_role": None,
                    "speakers": speakers,
                    "primary_speaker": primary_speaker(speakers),
                    "source_segments": [],
                    "dead_air_removed_sec": 0.0,
                    "planned_duration_sec": None,
                    "visual_context": visual,
                    "semantic_vector": vectors[index],
                }
            )

    chosen = select_non_overlapping(
        candidates,
        target_duration_sec=body.target_duration_sec,
        max_clips=body.max_clips,
        min_clip_sec=body.min_clip_sec,
        max_clip_sec=body.max_clip_sec,
    )
    if not chosen:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "planner.no_viable_highlights",
                    "message": (
                        "No analyzed transcript units met the requested "
                        "clip constraints"
                    ),
                }
            },
        )

    narrative = await structure_narrative(
        objective=objective,
        project=project,
        candidates=chosen,
        target_audience=body.target_audience,
    )
    chosen_by_key = {_candidate_key(item): item for item in chosen}
    ordered: list[dict] = []

    for key in narrative.get("ordered_keys") or []:
        candidate = chosen_by_key.get(key)
        if candidate:
            candidate["narrative_role"] = (
                narrative.get("roles") or {}
            ).get(key, "body")
            ordered.append(candidate)

    seen = {_candidate_key(item) for item in ordered}
    for candidate in sorted(
        chosen,
        key=lambda item: (item["asset_id"], item["start"]),
    ):
        if _candidate_key(candidate) not in seen:
            candidate["narrative_role"] = (
                narrative.get("roles") or {}
            ).get(_candidate_key(candidate), "body")
            ordered.append(candidate)

    ordered = rebalance_speaker_runs(
        ordered,
        max_same_speaker_run=body.max_same_speaker_run,
    )

    sequence = next(
        (
            seq
            for seq in state["sequences"]
            if seq["id"] == state["active_sequence_id"]
        ),
        None,
    )
    if not sequence:
        raise HTTPException(
            status_code=409,
            detail="Active sequence is unavailable",
        )

    video_track = next(
        (
            track
            for track in sequence["tracks"]
            if track["kind"] == "video"
        ),
        None,
    )
    if not video_track:
        raise HTTPException(
            status_code=409,
            detail="Active sequence has no video track",
        )

    overlay_track = next(
        (
            track
            for track in sequence["tracks"]
            if track["kind"] == "overlay" and not track.get("locked")
        ),
        None,
    )
    audio_track = next(
        (
            track
            for track in sequence["tracks"]
            if track["kind"] == "audio" and not track.get("locked")
        ),
        None,
    )
    music_asset = None
    if body.music_asset_id:
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
        music_asset = await db.assets.find_one(
            {
                "id": body.music_asset_id,
                "user_id": user_id,
                "processing_status": "ready",
            },
            {"_id": 0, "id": 1, "kind": 1, "duration_sec": 1},
        )
        if not music_asset:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "planner.music_asset_unavailable",
                        "message": "Selected music asset is not available or ready",
                    }
                },
            )
        if music_asset.get("kind") != "audio":
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

    timeline_cursor = 0
    operations: list[dict] = []
    broll_recommendations: list[dict] = []

    for candidate in ordered:
        role = candidate.get("narrative_role") or "body"
        semantic_vector = candidate.pop("semantic_vector")
        record = records_by_id.get(candidate["intelligence_id"]) or {}
        silences = record.get("silences") or []

        if body.remove_dead_air:
            source_segments, dead_air_removed = compact_source_ranges(
                start=float(candidate["start"]),
                end=float(candidate["end"]),
                silences=silences,
                min_dead_air_sec=body.dead_air_min_sec,
            )
        else:
            source_segments = [
                {
                    "start": float(candidate["start"]),
                    "end": float(candidate["end"]),
                }
            ]
            dead_air_removed = 0.0

        candidate["source_segments"] = source_segments
        candidate["dead_air_removed_sec"] = dead_air_removed
        if dead_air_removed > 0:
            candidate.setdefault("reasons", []).append(
                f"removed {dead_air_removed:.2f}s internal dead air"
            )

        candidate_timeline_start = timeline_cursor
        part_count = len(source_segments)
        for part_index, source_segment in enumerate(source_segments):
            source_start = round(
                float(source_segment["start"]) * ticks_per_second
            )
            part_duration = max(
                1,
                round(
                    (
                        float(source_segment["end"])
                        - float(source_segment["start"])
                    )
                    * ticks_per_second
                ),
            )
            operations.append(
                {
                    "operation": "add_clip",
                    "payload": {
                        "sequence_id": sequence["id"],
                        "track_id": video_track["id"],
                        "asset_id": candidate["asset_id"],
                        "timeline_start": timeline_cursor,
                        "duration": part_duration,
                        "source_start": source_start,
                        "source_duration": part_duration,
                        "metadata": {
                            "ai_plan": True,
                            "source_intelligence_id": candidate[
                                "intelligence_id"
                            ],
                            "source_unit_index": candidate["unit_index"],
                            "source_part_index": part_index,
                            "source_part_count": part_count,
                            "dead_air_removed_sec": dead_air_removed,
                            "highlight_score": candidate["final_score"],
                            "narrative_role": role,
                            "speakers": candidate.get("speakers") or [],
                            "primary_speaker": candidate.get(
                                "primary_speaker"
                            ),
                            "visual_context": candidate.get(
                                "visual_context"
                            ),
                        },
                    },
                    "reason": (
                        f"{role.title()} source part "
                        f"{part_index + 1}/{part_count} selected from "
                        f"grounded evidence with score "
                        f"{candidate['final_score']:.3f}: "
                        f"{candidate['text'][:180]}"
                    ),
                }
            )
            timeline_cursor += part_duration

        candidate_duration = timeline_cursor - candidate_timeline_start
        candidate["planned_duration_sec"] = round(
            candidate_duration / ticks_per_second,
            6,
        )

        beat_grid = record.get("beat_grid") or None
        timing_signal = "energy_onset"
        timing_events = record.get("rhythm_events") or []
        if beat_grid and beat_grid.get("beats"):
            timing_signal = "beat_grid"
            timing_events = [
                {
                    "time": beat,
                    "strength": float(beat_grid.get("confidence") or 0.0),
                }
                for beat in beat_grid["beats"]
            ]

        mapped_rhythm = map_rhythm_to_timeline(
            source_segments=source_segments,
            rhythm_events=timing_events,
            timeline_start=candidate_timeline_start,
            ticks_per_second=ticks_per_second,
        )
        broll_timeline_start = candidate_timeline_start
        rhythm_event = None
        if body.rhythm_snap_broll:
            broll_timeline_start, rhythm_event = snap_forward_to_rhythm(
                desired_tick=candidate_timeline_start,
                rhythm_events=mapped_rhythm,
                max_delay_ticks=round(
                    body.rhythm_snap_window_sec * ticks_per_second
                ),
                min_strength=0.05,
            )
            if rhythm_event:
                rhythm_event = {
                    **rhythm_event,
                    "signal": timing_signal,
                    "bpm": (
                        beat_grid.get("bpm")
                        if timing_signal == "beat_grid"
                        else None
                    ),
                    "confidence": (
                        beat_grid.get("confidence")
                        if timing_signal == "beat_grid"
                        else rhythm_event.get("strength")
                    ),
                }

        broll = recommend_broll_for_highlight(
            highlight=candidate,
            visual_candidates=visual_candidates,
            highlight_vector=semantic_vector,
            limit=3,
        )
        broll_available_duration = max(
            0,
            candidate_timeline_start
            + candidate_duration
            - broll_timeline_start,
        )
        if broll:
            broll_recommendations.append(
                {
                    "for_asset_id": candidate["asset_id"],
                    "for_unit_index": candidate["unit_index"],
                    "timeline_start": broll_timeline_start,
                    "duration": max(1, broll_available_duration),
                    "candidates": broll,
                    "rhythm_event": rhythm_event,
                }
            )

        if overlay_track and broll and broll_available_duration > 0:
            best = broll[0]
            broll_asset = assets.get(best["asset_id"])
            source_range = bounded_broll_source_range(
                observation_time_sec=float(best["time"]),
                asset_duration_sec=float(
                    (broll_asset or {}).get("duration_sec") or 0.0
                ),
                target_duration_ticks=min(
                    broll_available_duration,
                    max(1, round(3.0 * ticks_per_second)),
                ),
                ticks_per_second=ticks_per_second,
            )
            if source_range:
                broll_source_start, broll_duration = source_range
                fade_ticks = 0
                fade_meta = {"strategy": "disabled"}
                if body.broll_fade:
                    fade_ticks, fade_meta = broll_fade_ticks(
                        clip_duration_ticks=broll_duration,
                        ticks_per_second=ticks_per_second,
                        requested_fade_sec=body.broll_fade_sec,
                        rhythm_event=rhythm_event,
                    )
                transition = (
                    {"kind": "fade", "duration": fade_ticks}
                    if fade_ticks > 0
                    else None
                )
                operations.append(
                    {
                        "operation": "add_broll_overlay",
                        "payload": {
                            "sequence_id": sequence["id"],
                            "track_id": overlay_track["id"],
                            "asset_id": best["asset_id"],
                            "timeline_start": broll_timeline_start,
                            "duration": broll_duration,
                            "source_start": broll_source_start,
                            "source_duration": broll_duration,
                            "volume": 0.0,
                            "transition_in": transition,
                            "transition_out": transition,
                            "metadata": {
                                "ai_plan": True,
                                "broll": True,
                                "source_intelligence_id": best[
                                    "intelligence_id"
                                ],
                                "source_observation_index": best[
                                    "observation_index"
                                ],
                                "broll_relevance_score": best[
                                    "relevance_score"
                                ],
                                "replaces_primary_visual": True,
                                "rhythm_snapped": rhythm_event is not None,
                                "rhythm_source_time": (
                                    rhythm_event.get("source_time")
                                    if rhythm_event
                                    else None
                                ),
                                "rhythm_strength": (
                                    rhythm_event.get("strength")
                                    if rhythm_event
                                    else None
                                ),
                                "rhythm_signal": (
                                    rhythm_event.get("signal")
                                    if rhythm_event
                                    else None
                                ),
                                "rhythm_bpm": (
                                    rhythm_event.get("bpm")
                                    if rhythm_event
                                    else None
                                ),
                                "rhythm_confidence": (
                                    rhythm_event.get("confidence")
                                    if rhythm_event
                                    else None
                                ),
                                "transition_strategy": fade_meta.get(
                                    "strategy"
                                ),
                                "transition_fade_ticks": fade_ticks,
                                "transition_fade_sec": fade_meta.get(
                                    "planned_fade_sec"
                                ),
                            },
                        },
                        "reason": (
                            f"Grounded B-roll from {best['asset_id']} at "
                            f"{best['time']:.3f}s matched this spoken "
                            f"highlight with similarity "
                            f"{best['relevance_score']:.3f}"
                            + (
                                " and its entrance was snapped to a "
                                "nearby measured audio onset"
                                if rhythm_event
                                else ""
                            )
                            + (
                                f" with {fade_meta.get('strategy')} "
                                "fade transitions"
                                if fade_ticks > 0
                                else ""
                            )
                        ),
                    }
                )

        if body.include_captions:
            caption_text = candidate["text"].strip()[:500]
            operations.append(
                {
                    "operation": "add_caption",
                    "payload": {
                        "sequence_id": sequence["id"],
                        "start": candidate_timeline_start,
                        "duration": candidate_duration,
                        "text": caption_text,
                        "style": {
                            "source": "transcript",
                            "narrative_role": role,
                            "speaker": candidate.get("primary_speaker"),
                        },
                    },
                    "reason": (
                        "Grounded caption copied from the selected "
                        "transcript unit"
                    ),
                }
            )

    if music_asset:
        output_duration = timeline_cursor
        music_source_start = round(
            body.music_source_start_sec * ticks_per_second
        )
        music_duration_ticks = round(
            float(music_asset.get("duration_sec") or 0.0)
            * ticks_per_second
        )
        if output_duration <= 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "planner.empty_output",
                        "message": "Music cannot be added to an empty output timeline",
                    }
                },
            )
        if music_source_start >= music_duration_ticks:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "planner.music_source_start_out_of_bounds",
                        "message": "Music source start must be inside the selected asset",
                        "asset_id": music_asset["id"],
                        "source_start_sec": body.music_source_start_sec,
                    }
                },
            )

        music_fade_ticks, music_fade_meta = bounded_fade_ticks(
            clip_duration_ticks=output_duration,
            ticks_per_second=ticks_per_second,
            requested_fade_sec=body.music_fade_sec,
        )

        remaining_music_ticks = music_duration_ticks - music_source_start
        if (
            body.music_fit_mode == "strict"
            and output_duration > remaining_music_ticks + 1
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "planner.music_asset_too_short",
                        "message": (
                            "Selected music does not have enough remaining "
                            "duration to cover the planned output in strict mode"
                        ),
                        "asset_id": music_asset["id"],
                        "required_duration_sec": round(
                            output_duration / ticks_per_second,
                            3,
                        ),
                        "available_duration_sec": round(
                            remaining_music_ticks / ticks_per_second,
                            3,
                        ),
                        "source_start_sec": body.music_source_start_sec,
                    }
                },
            )

        requested_crossfade_ticks = round(
            body.music_loop_crossfade_sec * ticks_per_second
        )
        try:
            if body.music_fit_mode == "loop":
                music_segments, fit_meta = plan_loop_segments(
                    output_duration_ticks=output_duration,
                    asset_duration_ticks=music_duration_ticks,
                    source_start_ticks=music_source_start,
                    requested_crossfade_ticks=requested_crossfade_ticks,
                )
            else:
                music_segments = [
                    {
                        "timeline_start": 0,
                        "duration": output_duration,
                        "source_start": music_source_start,
                        "source_duration": output_duration,
                    }
                ]
                fit_meta = {
                    "fit_mode": "strict",
                    "segment_count": 1,
                    "loop_count": 0,
                    "crossfade_ticks": 0,
                }
        except MusicFitError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "planner.music_fit_invalid",
                        "message": str(exc),
                        "asset_id": music_asset["id"],
                    }
                },
            ) from exc

        music_segments = attach_loop_transitions(
            music_segments,
            seam_crossfade_ticks=int(fit_meta.get("crossfade_ticks") or 0),
            intro_fade_ticks=music_fade_ticks,
            outro_fade_ticks=music_fade_ticks,
        )
        music_ducking = {
            "enabled": body.music_ducking,
            "threshold": body.music_duck_threshold,
            "ratio": body.music_duck_ratio,
            "attack_ms": body.music_duck_attack_ms,
            "release_ms": body.music_duck_release_ms,
            "makeup": 1.0,
        }
        operations.append(
            {
                "operation": "add_music_bed",
                "payload": {
                    "sequence_id": sequence["id"],
                    "track_id": audio_track["id"],
                    "asset_id": music_asset["id"],
                    "timeline_start": 0,
                    "duration": output_duration,
                    "volume": body.music_volume,
                    "segments": music_segments,
                    "ducking": music_ducking,
                    "metadata": {
                        "ai_plan": True,
                        "music_bed": True,
                        "user_selected_music": True,
                        "music_volume": body.music_volume,
                        "music_source_start_sec": body.music_source_start_sec,
                        "music_fit_mode": fit_meta.get("fit_mode"),
                        "music_segment_count": fit_meta.get("segment_count"),
                        "music_loop_count": fit_meta.get("loop_count"),
                        "music_loop_crossfade_ticks": fit_meta.get(
                            "crossfade_ticks"
                        ),
                        "music_loop_crossfade_sec": round(
                            int(fit_meta.get("crossfade_ticks") or 0)
                            / ticks_per_second,
                            6,
                        ),
                        "transition_strategy": music_fade_meta.get("strategy"),
                        "transition_fade_ticks": music_fade_ticks,
                        "transition_fade_sec": music_fade_meta.get(
                            "planned_fade_sec"
                        ),
                    },
                },
                "reason": (
                    "User-selected music bed fitted to the complete planned "
                    "output with deterministic volume, fades"
                    + (
                        f", and {fit_meta.get('loop_count')} crossfaded loop seam(s)"
                        if int(fit_meta.get("loop_count") or 0) > 0
                        else ""
                    )
                    + (
                        " with speech-responsive ducking"
                        if body.music_ducking
                        else ""
                    )
                ),
            }
        )

    assign_operation_ids(operations)
    now = utc_now()
    plan = {
        "id": str(uuid.uuid4()),
        "project_id": project["id"],
        "user_id": user_id,
        "project_state_version": state["version"],
        "status": "proposed",
        "objective": objective,
        "target_duration_sec": body.target_duration_sec,
        "candidates": ordered,
        "operations": operations,
        "broll_recommendations": broll_recommendations,
        "audience_profile": narrative.get("audience_profile") or {},
        "narrative_summary": str(
            narrative.get("narrative_summary") or ""
        ),
        "caption_suggestion": str(
            narrative.get("caption_suggestion") or ""
        ),
        "cta_suggestion": str(narrative.get("cta_suggestion") or ""),
        "narrative_provider": narrative.get("provider"),
        "narrative_model": narrative.get("model"),
        "evaluation": {},
        "created_at": now,
        "updated_at": now,
    }
    plan["evaluation"] = evaluate_plan(plan)
    return plan
