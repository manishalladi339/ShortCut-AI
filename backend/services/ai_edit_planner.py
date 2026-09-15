"""Grounded Create-For-Me edit proposal builder."""
from __future__ import annotations

import uuid
from fastapi import HTTPException
from core.config import settings
from core.security import utc_now
from db.mongo import get_db
from models.ai_plan import CreateAIEditPlanRequest
from services.broll_planning import bounded_broll_source_range, build_visual_candidates, recommend_broll_for_highlight
from services.embeddings import get_embedding_provider
from services.highlight_scoring import combine_scores, heuristic_highlight_score, select_non_overlapping
from services.narrative_planning import structure_narrative
from services.planner_evaluation import evaluate_plan
from services.semantic_search import cosine_similarity
from services.silence_editing import snap_outward_to_silence
from services.speaker_editing import normalize_speakers, primary_speaker, speaker_allowed


def _candidate_key(item: dict) -> str:
    return f"{item['asset_id']}:{item['unit_index']}"


def _nearest_visual(record: dict, start: float, end: float) -> dict | None:
    observations = record.get("visual_observations") or []
    if not observations:
        return None
    midpoint = start + (end - start) / 2.0
    nearby = min(observations, key=lambda item: abs(float(item.get("time") or 0.0) - midpoint))
    return nearby if abs(float(nearby.get("time") or 0.0) - midpoint) <= 12.0 else None


async def build_plan(*, project: dict, user_id: str, state: dict, body: CreateAIEditPlanRequest) -> dict:
    db = get_db()
    records = await db.media_intelligence.find({"project_id": project["id"], "user_id": user_id, "status": "completed", "embedding_model": settings.EMBEDDING_MODEL}, {"_id": 0}).to_list(500)
    if not records:
        raise HTTPException(status_code=409, detail={"error": {"code": "planner.no_intelligence", "message": "Analyze at least one project media asset before creating an AI edit plan"}})
    objective = (body.objective or "").strip() or (project.get("prompt") or "").strip() or (project.get("description") or "").strip() or f"Create a strong {project.get('content_type', 'short-form')} edit"
    query_vector = (await get_embedding_provider().embed([objective]))[0]
    asset_ids = [record["asset_id"] for record in records]
    asset_docs = await db.assets.find({"id": {"$in": asset_ids}, "user_id": user_id}, {"_id": 0, "id": 1, "duration_sec": 1, "kind": 1}).to_list(len(asset_ids))
    assets = {asset["id"]: asset for asset in asset_docs}
    visual_candidates = [candidate for record in records for candidate in build_visual_candidates(record)]
    candidates = []
    for record in records:
        units, vectors = record.get("semantic_units") or [], record.get("semantic_vectors") or []
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
                    visual_bonus += 0.025; reasons.append("nearby visual context available")
                if visual.get("text_on_screen"):
                    visual_bonus += 0.015; reasons.append("nearby on-screen text")
            final = min(1.0, combine_scores(heuristic, relevance) + visual_bonus)
            candidates.append({"asset_id": record["asset_id"], "intelligence_id": record["id"], "unit_index": index, "start": refined_start, "end": refined_end, "text": unit["text"], "heuristic_score": heuristic, "relevance_score": relevance, "final_score": final, "reasons": reasons + ["semantic relevance to objective"], "narrative_role": None, "speakers": speakers, "primary_speaker": primary_speaker(speakers), "visual_context": visual, "semantic_vector": vectors[index]})
    chosen = select_non_overlapping(candidates, target_duration_sec=body.target_duration_sec, max_clips=body.max_clips, min_clip_sec=body.min_clip_sec, max_clip_sec=body.max_clip_sec)
    if not chosen:
        raise HTTPException(status_code=422, detail={"error": {"code": "planner.no_viable_highlights", "message": "No analyzed transcript units met the requested clip constraints"}})
    narrative = await structure_narrative(objective=objective, project=project, candidates=chosen, target_audience=body.target_audience)
    chosen_by_key = {_candidate_key(item): item for item in chosen}
    ordered = []
    for key in narrative.get("ordered_keys") or []:
        candidate = chosen_by_key.get(key)
        if candidate:
            candidate["narrative_role"] = (narrative.get("roles") or {}).get(key, "body"); ordered.append(candidate)
    seen = {_candidate_key(item) for item in ordered}
    for candidate in sorted(chosen, key=lambda item: (item["asset_id"], item["start"])):
        if _candidate_key(candidate) not in seen:
            candidate["narrative_role"] = (narrative.get("roles") or {}).get(_candidate_key(candidate), "body"); ordered.append(candidate)
    sequence = next((seq for seq in state["sequences"] if seq["id"] == state["active_sequence_id"]), None)
    if not sequence: raise HTTPException(status_code=409, detail="Active sequence is unavailable")
    video_track = next((track for track in sequence["tracks"] if track["kind"] == "video"), None)
    if not video_track: raise HTTPException(status_code=409, detail="Active sequence has no video track")
    overlay_track = next((track for track in sequence["tracks"] if track["kind"] == "overlay" and not track.get("locked")), None)
    ticks_per_second = sequence["timebase"]["numerator"] / sequence["timebase"]["denominator"]
    timeline_cursor, operations, broll_recommendations = 0, [], []
    for candidate in ordered:
        source_start = round(candidate["start"] * ticks_per_second)
        duration = max(1, round((candidate["end"] - candidate["start"]) * ticks_per_second))
        role = candidate.get("narrative_role") or "body"
        semantic_vector = candidate.pop("semantic_vector")
        broll = recommend_broll_for_highlight(highlight=candidate, visual_candidates=visual_candidates, highlight_vector=semantic_vector, limit=3)
        if broll:
            broll_recommendations.append({"for_asset_id": candidate["asset_id"], "for_unit_index": candidate["unit_index"], "timeline_start": timeline_cursor, "duration": duration, "candidates": broll})
        operations.append({"operation": "add_clip", "payload": {"sequence_id": sequence["id"], "track_id": video_track["id"], "asset_id": candidate["asset_id"], "timeline_start": timeline_cursor, "duration": duration, "source_start": source_start, "source_duration": duration, "metadata": {"ai_plan": True, "source_intelligence_id": candidate["intelligence_id"], "source_unit_index": candidate["unit_index"], "highlight_score": candidate["final_score"], "narrative_role": role, "speakers": candidate.get("speakers") or [], "primary_speaker": candidate.get("primary_speaker"), "visual_context": candidate.get("visual_context")}}, "reason": f"{role.title()} clip selected from grounded multimodal evidence with score {candidate['final_score']:.3f}: {candidate['text'][:180]}"})
        if overlay_track and broll:
            best = broll[0]
            broll_asset = assets.get(best["asset_id"])
            source_range = bounded_broll_source_range(
                observation_time_sec=float(best["time"]),
                asset_duration_sec=float((broll_asset or {}).get("duration_sec") or 0.0),
                target_duration_ticks=min(
                    duration, max(1, round(3.0 * ticks_per_second))
                ),
                ticks_per_second=ticks_per_second,
            )
            if source_range:
                broll_source_start, broll_duration = source_range
                operations.append(
                    {
                        "operation": "add_broll_overlay",
                        "payload": {
                            "sequence_id": sequence["id"],
                            "track_id": overlay_track["id"],
                            "asset_id": best["asset_id"],
                            "timeline_start": timeline_cursor,
                            "duration": broll_duration,
                            "source_start": broll_source_start,
                            "source_duration": broll_duration,
                            "volume": 0.0,
                            "metadata": {
                                "ai_plan": True,
                                "broll": True,
                                "source_intelligence_id": best["intelligence_id"],
                                "source_observation_index": best["observation_index"],
                                "broll_relevance_score": best["relevance_score"],
                                "replaces_primary_visual": True,
                            },
                        },
                        "reason": (
                            f"Grounded B-roll from {best['asset_id']} at "
                            f"{best['time']:.3f}s matched this spoken highlight "
                            f"with similarity {best['relevance_score']:.3f}"
                        ),
                    }
                )
        if body.include_captions:
            caption_text = candidate["text"].strip()[:500]
            operations.append({"operation": "add_caption", "payload": {"sequence_id": sequence["id"], "start": timeline_cursor, "duration": duration, "text": caption_text, "style": {"source": "transcript", "narrative_role": role, "speaker": candidate.get("primary_speaker")}}, "reason": "Grounded caption copied from the selected transcript unit"})
        timeline_cursor += duration
    now = utc_now()
    plan = {"id": str(uuid.uuid4()), "project_id": project["id"], "user_id": user_id, "project_state_version": state["version"], "status": "proposed", "objective": objective, "target_duration_sec": body.target_duration_sec, "candidates": ordered, "operations": operations, "broll_recommendations": broll_recommendations, "audience_profile": narrative.get("audience_profile") or {}, "narrative_summary": str(narrative.get("narrative_summary") or ""), "caption_suggestion": str(narrative.get("caption_suggestion") or ""), "cta_suggestion": str(narrative.get("cta_suggestion") or ""), "narrative_provider": narrative.get("provider"), "narrative_model": narrative.get("model"), "evaluation": {}, "created_at": now, "updated_at": now}
    plan["evaluation"] = evaluate_plan(plan)
    return plan
