"""Public-release resource limits for uploads and expensive workloads."""
from __future__ import annotations

from fastapi import HTTPException, status

from core.config import settings
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
