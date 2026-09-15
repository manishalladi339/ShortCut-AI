"""Grounded Create-For-Me edit proposal builder."""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from core.config import settings
from core.security import utc_now
from db.mongo import get_db
from models.ai_plan import CreateAIEditPlanRequest
from services.embeddings import get_embedding_provider
from services.highlight_scoring import (
    combine_scores,
    heuristic_highlight_score,
    select_non_overlapping,
)
from services.semantic_search import cosine_similarity


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
                    "message": "Analyze at least one project media asset before creating an AI edit plan",
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

    candidates: list[dict] = []
    for record in records:
        units = record.get("semantic_units") or []
        vectors = record.get("semantic_vectors") or []
        asset = assets.get(record["asset_id"])
        if not asset or asset.get("kind") != "video":
            continue

        for index, unit in enumerate(units):
            if index >= len(vectors):
                continue
            heuristic, reasons = heuristic_highlight_score(
                unit,
                asset_duration_sec=asset.get("duration_sec"),
            )
            relevance = cosine_similarity(query_vector, vectors[index])
            final = combine_scores(heuristic, relevance)
            candidates.append(
                {
                    "asset_id": record["asset_id"],
                    "intelligence_id": record["id"],
                    "unit_index": index,
                    "start": float(unit["start"]),
                    "end": float(unit["end"]),
                    "text": unit["text"],
                    "heuristic_score": heuristic,
                    "relevance_score": relevance,
                    "final_score": final,
                    "reasons": reasons + ["semantic relevance to objective"],
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
                    "message": "No analyzed transcript units met the requested clip constraints",
                }
            },
        )

    sequence = next(
        (seq for seq in state["sequences"] if seq["id"] == state["active_sequence_id"]),
        None,
    )
    if not sequence:
        raise HTTPException(status_code=409, detail="Active sequence is unavailable")
    video_track = next(
        (track for track in sequence["tracks"] if track["kind"] == "video"),
        None,
    )
    if not video_track:
        raise HTTPException(status_code=409, detail="Active sequence has no video track")

    ticks_per_second = sequence["timebase"]["numerator"] / sequence["timebase"]["denominator"]
    timeline_cursor = 0
    operations: list[dict] = []

    # Rank determines selection; timeline is reordered by source chronology to avoid
    # a random-feeling cut sequence before an LLM narrative planner is introduced.
    ordered = sorted(chosen, key=lambda item: (item["asset_id"], item["start"]))
    for candidate in ordered:
        source_start = round(candidate["start"] * ticks_per_second)
        duration = max(1, round((candidate["end"] - candidate["start"]) * ticks_per_second))
        operations.append(
            {
                "operation": "add_clip",
                "payload": {
                    "sequence_id": sequence["id"],
                    "track_id": video_track["id"],
                    "asset_id": candidate["asset_id"],
                    "timeline_start": timeline_cursor,
                    "duration": duration,
                    "source_start": source_start,
                    "source_duration": duration,
                    "metadata": {
                        "ai_plan": True,
                        "source_intelligence_id": candidate["intelligence_id"],
                        "source_unit_index": candidate["unit_index"],
                        "highlight_score": candidate["final_score"],
                    },
                },
                "reason": (
                    f"Selected grounded transcript moment with score "
                    f"{candidate['final_score']:.3f}: {candidate['text'][:180]}"
                ),
            }
        )
        timeline_cursor += duration

    now = utc_now()
    return {
        "id": str(uuid.uuid4()),
        "project_id": project["id"],
        "user_id": user_id,
        "project_state_version": state["version"],
        "status": "proposed",
        "objective": objective,
        "target_duration_sec": body.target_duration_sec,
        "candidates": sorted(
            chosen,
            key=lambda item: (-item["final_score"], item["asset_id"], item["start"]),
        ),
        "operations": operations,
        "created_at": now,
        "updated_at": now,
    }
