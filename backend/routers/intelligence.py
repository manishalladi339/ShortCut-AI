"""Media-intelligence API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.job import JobType
from models.media_intelligence import AnalyzeAssetOut, MediaIntelligenceOut
from services import job_service

router = APIRouter(prefix="/assets", tags=["media-intelligence"])


async def _owned_ready_asset(asset_id: str, user_id: str) -> dict:
    asset = await get_db().assets.find_one(
        {"id": asset_id, "user_id": user_id}, {"_id": 0}
    )
    if not asset:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "resource.not_found", "message": "Asset not found"}
            },
        )
    if asset.get("processing_status") != "ready":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "intelligence.asset_not_ready",
                    "message": "Asset is still processing",
                }
            },
        )
    if asset.get("kind") not in {"video", "audio"}:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "intelligence.unsupported_asset",
                    "message": "Only video/audio assets are supported",
                }
            },
        )
    return asset


@router.post(
    "/{asset_id}/analyze",
    response_model=AnalyzeAssetOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_asset(
    asset_id: str,
    user: dict = Depends(get_current_user),
) -> AnalyzeAssetOut:
    db = get_db()
    asset = await _owned_ready_asset(asset_id, user["id"])

    existing = await db.media_intelligence.find_one(
        {
            "asset_id": asset_id,
            "user_id": user["id"],
            "status": {"$in": ["queued", "running"]},
        },
        {"_id": 0},
    )
    if existing:
        return AnalyzeAssetOut(
            job_id=existing["job_id"],
            intelligence_id=existing["id"],
            status=existing["status"],
        )

    now = utc_now()
    intelligence_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    async def enqueue_analysis():
        return await job_service.enqueue(
            user_id=user["id"],
            project_id=asset.get("project_id"),
            asset_id=asset_id,
            job_type=JobType.media_intelligence,
            payload={"intelligence_id": intelligence_id},
            max_attempts=2,
            job_id=job_id,
        )

    doc = {
        "id": intelligence_id,
        "asset_id": asset_id,
        "user_id": user["id"],
        "project_id": asset.get("project_id"),
        "job_id": job_id,
        "status": "queued",
        "language": None,
        "transcript_text": "",
        "words": [],
        "segments": [],
        "scenes": [],
        "semantic_units": [],
        "provider": None,
        "model": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.media_intelligence.insert_one(doc)
    await enqueue_analysis()
    return AnalyzeAssetOut(
        job_id=job_id,
        intelligence_id=intelligence_id,
        status="queued",
    )


@router.get("/{asset_id}/intelligence", response_model=MediaIntelligenceOut)
async def get_asset_intelligence(
    asset_id: str,
    user: dict = Depends(get_current_user),
) -> MediaIntelligenceOut:
    await _owned_ready_asset(asset_id, user["id"])
    doc = await get_db().media_intelligence.find_one(
        {"asset_id": asset_id, "user_id": user["id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "intelligence.not_found",
                    "message": "No analysis exists for this asset",
                }
            },
        )
    return MediaIntelligenceOut(**doc)
