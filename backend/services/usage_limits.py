"""Public-release resource limits for uploads and expensive workloads."""
from __future__ import annotations

from fastapi import HTTPException, status

from core.config import settings
from core.security import utc_now
from db.mongo import get_db


async def enforce_upload_limits(*, user_id: str, requested_bytes: int) -> None:
    if requested_bytes > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": {
                    "code": "upload.file_too_large",
                    "message": "This file is larger than the current upload limit.",
                }
            },
        )

    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": None, "total": {"$sum": "$size_bytes"}}},
    ]
    rows = await get_db().assets.aggregate(pipeline).to_list(1)
    used = int(rows[0]["total"]) if rows else 0
    if used + requested_bytes > settings.MAX_USER_STORAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": {
                    "code": "upload.storage_quota_exceeded",
                    "message": "Your current storage allowance has been reached.",
                }
            },
        )


async def enforce_confirmed_upload_size(
    *, user_id: str, asset_id: str, actual_bytes: int
) -> None:
    if actual_bytes > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": {
                    "code": "upload.file_too_large",
                    "message": "The uploaded file exceeds the current size limit.",
                }
            },
        )

    pipeline = [
        {"$match": {"user_id": user_id, "id": {"$ne": asset_id}}},
        {"$group": {"_id": None, "total": {"$sum": "$size_bytes"}}},
    ]
    rows = await get_db().assets.aggregate(pipeline).to_list(1)
    used = int(rows[0]["total"]) if rows else 0
    if used + actual_bytes > settings.MAX_USER_STORAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": {
                    "code": "upload.storage_quota_exceeded",
                    "message": "Your current storage allowance has been reached.",
                }
            },
        )


def validate_media_duration(*, kind: str, duration_sec: float | None) -> None:
    if duration_sec is None:
        return
    if kind == "video" and duration_sec > settings.MAX_VIDEO_DURATION_SEC:
        raise ValueError(
            f"video duration exceeds {settings.MAX_VIDEO_DURATION_SEC} seconds"
        )
    if kind == "audio" and duration_sec > settings.MAX_AUDIO_DURATION_SEC:
        raise ValueError(
            f"audio duration exceeds {settings.MAX_AUDIO_DURATION_SEC} seconds"
        )


async def enforce_render_concurrency(*, user_id: str) -> None:
    active = await get_db().exports.count_documents(
        {"user_id": user_id, "status": {"$in": ["queued", "rendering"]}}
    )
    if active >= settings.MAX_ACTIVE_RENDERS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "render.concurrent_limit",
                    "message": "You already have the maximum number of active renders.",
                }
            },
        )


async def _enforce_daily_free_limit(
    *,
    user: dict,
    collection_name: str,
    limit: int,
    code: str,
    message: str,
) -> None:
    """Cap cost-generating work per UTC day for free-beta accounts."""
    tier = user.get("subscription_tier", "free")
    if getattr(tier, "value", tier) != "free":
        return
    day_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = await get_db()[collection_name].count_documents(
        {"user_id": user["id"], "created_at": {"$gte": day_start}}
    )
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": code, "message": message}},
        )


async def enforce_daily_intelligence_limit(*, user: dict) -> None:
    await _enforce_daily_free_limit(
        user=user,
        collection_name="media_intelligence",
        limit=settings.MAX_DAILY_INTELLIGENCE_JOBS_FREE,
        code="usage.daily_intelligence_limit",
        message="Daily media-analysis limit reached for the free beta.",
    )


async def enforce_daily_render_limit(*, user: dict) -> None:
    await _enforce_daily_free_limit(
        user=user,
        collection_name="exports",
        limit=settings.MAX_DAILY_RENDER_JOBS_FREE,
        code="usage.daily_render_limit",
        message="Daily render limit reached for the free beta.",
    )


async def enforce_daily_ai_plan_limit(*, user: dict) -> None:
    await _enforce_daily_free_limit(
        user=user,
        collection_name="ai_edit_plans",
        limit=settings.MAX_DAILY_AI_PLANS_FREE,
        code="usage.daily_ai_plan_limit",
        message="Daily AI Director plan limit reached for the free beta.",
    )
