"""Project-scoped semantic retrieval over analyzed media."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.config import settings
from core.deps import get_current_user
from db.mongo import get_db
from models.retrieval import SemanticSearchOut, SemanticSearchRequest
from services.embeddings import get_embedding_provider
from services.semantic_search import rank_units

router = APIRouter(prefix="/projects", tags=["retrieval"])


@router.post("/{project_id}/intelligence/search", response_model=SemanticSearchOut)
async def search_project_media(
    project_id: str,
    body: SemanticSearchRequest,
    user: dict = Depends(get_current_user),
) -> SemanticSearchOut:
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id, "user_id": user["id"]},
        {"_id": 0, "id": 1},
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )

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
        return SemanticSearchOut(
            query=body.query,
            model=settings.EMBEDDING_MODEL,
            hits=[],
        )

    query_vector = (await get_embedding_provider().embed([body.query]))[0]
    hits = rank_units(
        query_vector,
        candidates,
        limit=body.limit,
        min_score=body.min_score,
    )
    return SemanticSearchOut(
        query=body.query,
        model=settings.EMBEDDING_MODEL,
        hits=hits,
    )
