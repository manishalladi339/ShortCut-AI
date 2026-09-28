"""Mongo-backed fixed-window rate limiting for public API abuse protection."""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, Request, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.security import utc_now
from db.mongo import get_db


def client_key(request: Request) -> str:
    """Return a stable network key without trusting spoofable forwarding headers."""
    client = request.client
    return client.host if client and client.host else "unknown"


async def enforce_rate_limit(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    if limit <= 0 or window_seconds <= 0:
        return

    now = utc_now()
    bucket = int(now.timestamp()) // window_seconds
    selector = {"scope": scope, "key": key, "bucket": bucket}
    update = {
        "$inc": {"count": 1},
        "$setOnInsert": {
            "created_at": now,
            "expires_at": now + timedelta(seconds=window_seconds * 2),
        },
    }

    try:
        doc = await get_db().rate_limits.find_one_and_update(
            selector,
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        doc = await get_db().rate_limits.find_one_and_update(
            selector,
            {"$inc": {"count": 1}},
            return_document=ReturnDocument.AFTER,
        )

    count = int((doc or {}).get("count", 0))
    if count > limit:
        retry_after = window_seconds - (int(now.timestamp()) % window_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(max(1, retry_after))},
            detail={
                "error": {
                    "code": "rate_limit.exceeded",
                    "message": "Too many requests. Please try again later.",
                }
            },
        )
