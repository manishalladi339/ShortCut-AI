"""Whole-project intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.deps import get_current_user
from db.mongo import get_db
from models.project_intelligence import ProjectIntelligenceOut
from services.project_intelligence import build_and_store_project_intelligence

router = APIRouter(prefix="/projects", tags=["project-intelligence"])


async def _owned_project(project_id: str, user_id: str) -> dict:
    project = await get_db().projects.find_one(
        {"id": project_id, "user_id": user_id, "archived": False},
        {"_id": 0},
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )
    return project


@router.post("/{project_id}/project-intelligence", response_model=ProjectIntelligenceOut)
async def rebuild_project_intelligence(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> ProjectIntelligenceOut:
    await _owned_project(project_id, user["id"])
    db = get_db()
    records = await db.media_intelligence.find(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "status": "completed",
        },
        {"_id": 0},
    ).to_list(500)
    if not records:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "project_intelligence.no_media_intelligence",
                    "message": "Analyze project media before building project intelligence",
                }
            },
        )

    asset_ids = sorted({record["asset_id"] for record in records})
    assets = await db.assets.find(
        {"id": {"$in": asset_ids}, "user_id": user["id"]},
        {
            "_id": 0,
            "id": 1,
            "filename": 1,
            "kind": 1,
            "duration_sec": 1,
        },
    ).to_list(len(asset_ids))

    doc = await build_and_store_project_intelligence(
        project_id=project_id,
        user_id=user["id"],
        records=records,
        assets=assets,
    )
    return ProjectIntelligenceOut(**doc)


@router.get("/{project_id}/project-intelligence", response_model=ProjectIntelligenceOut)
async def get_project_intelligence(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> ProjectIntelligenceOut:
    await _owned_project(project_id, user["id"])
    doc = await get_db().project_intelligence.find_one(
        {"project_id": project_id, "user_id": user["id"]},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "project_intelligence.not_found",
                    "message": "Project intelligence has not been built yet",
                }
            },
        )
    return ProjectIntelligenceOut(**doc)
