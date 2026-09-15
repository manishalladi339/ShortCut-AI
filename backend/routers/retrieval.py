"""Project-scoped semantic and visual retrieval over analyzed media."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.config import settings
from core.deps import get_current_user
from db.mongo import get_db
from models.retrieval import (
    SemanticSearchOut,
    SemanticSearchRequest,
    VisualSearchOut,
)
from services.broll_planning import rank_broll_candidates
from services.embeddings import get_embedding_provider
from services.semantic_search import rank_units

router = APIRouter(prefix="/projects", tags=["retrieval"])


async def _require_project(project_id: str, user_id: str) -> None:
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id, "user_id": user_id},
        {"_id": 0, "id": 1},
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )


@router.post("/{project_id}/intelligence/search", response_model=SemanticSearchOut)
async def search_project_media(
    project_id: str,
    body: SemanticSearchRequest,
    user: dict = Depends(get_current_user),
) -> SemanticSearchOut:
    db = get_db()
    await _require_project(project_id, user["id"])

    records = await db.media_intelligence.find(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "status": "completed",
            "embedding_model": settings.EMBEDDING_MODEL,
        },
        {
            "_id": 0,
            "id": 1,
            "asset_id": 1,
            "semantic_units": 1,
            "semantic_vectors": 1,
        },
    ).to_list(500)

    candidates: list[dict] = []
    for record in records:
        units = record.get("semantic_units") or []
        vectors = record.get("semantic_vectors") or []
        for index, unit in enumerate(units):
            if index >= len(vectors):
                continue
            candidates.append(
                {
                    "asset_id": record["asset_id"],
                    "intelligence_id": record["id"],
                    "unit_index": index,
                    "start": float(unit["start"]),
                    "end": float(unit["end"]),
                    "text": unit["text"],
                    "embedding": vectors[index],
                }
            )

    if not candidates:
        return SemanticSearchOut(query=body.query, model=settings.EMBEDDING_MODEL, hits=[])

    query_vector = (await get_embedding_provider().embed([body.query]))[0]
    hits = rank_units(
        query_vector,
        candidates,
        limit=body.limit,
        min_score=body.min_score,
    )
    return SemanticSearchOut(query=body.query, model=settings.EMBEDDING_MODEL, hits=hits)


@router.post("/{project_id}/intelligence/visual-search", response_model=VisualSearchOut)
async def search_project_visuals(
    project_id: str,
    body: SemanticSearchRequest,
    user: dict = Depends(get_current_user),
) -> VisualSearchOut:
    """Find grounded visual moments suitable for B-roll/reference planning."""
    db = get_db()
    await _require_project(project_id, user["id"])
    records = await db.media_intelligence.find(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "status": "completed",
        },
        {"_id": 0, "id": 1, "asset_id": 1, "visual_observations": 1},
    ).to_list(500)

    raw: list[dict] = []
    descriptions: list[str] = []
    for record in records:
        for observation in record.get("visual_observations") or []:
            description = str(observation.get("description") or "").strip()
            if not description:
                continue
            raw.append(
                {
                    "asset_id": record["asset_id"],
                    "intelligence_id": record["id"],
                    "observation_index": int(observation.get("index") or 0),
                    "time": float(observation.get("time") or 0.0),
                    "description": description,
                    "shot_type": str(observation.get("shot_type") or "unknown"),
                    "visible_objects": observation.get("visible_objects") or [],
                    "text_on_screen": observation.get("text_on_screen"),
                }
            )
            descriptions.append(description)

    if not raw:
        return VisualSearchOut(query=body.query, model=settings.EMBEDDING_MODEL, hits=[])

    vectors = await get_embedding_provider().embed([body.query, *descriptions])
    query_vector, observation_vectors = vectors[0], vectors[1:]
    candidates = [
        item | {"vector": vector}
        for item, vector in zip(raw, observation_vectors)
    ]
    ranked = rank_broll_candidates(
        candidates,
        objective_vector=query_vector,
        limit=body.limit,
    )
    ranked = [item for item in ranked if item["relevance_score"] >= body.min_score]
    return VisualSearchOut(
        query=body.query,
        model=settings.EMBEDDING_MODEL,
        hits=ranked,
    )
