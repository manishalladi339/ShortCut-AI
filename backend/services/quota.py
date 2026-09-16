"""Atomic monthly project quota accounting."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument

from core.security import utc_now
from db.mongo import get_db


def quota_period(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m")


async def consume_project_slot(user_id: str) -> dict:
    """Atomically reset the monthly window when needed and consume one slot."""
    db = get_db()
    now = utc_now()
    period = quota_period(now)

    query = {
        "id": user_id,
        "$or": [
            {"monthly_project_limit": -1},
            {"quota_period": {"$ne": period}},
            {
                "$expr": {
                    "$lt": [
                        {"$ifNull": ["$monthly_project_count", 0]},
                        {"$ifNull": ["$monthly_project_limit", 3]},
                    ]
                }
            },
        ],
    }
    update = [
        {
            "$set": {
                "monthly_project_count": {
                    "$cond": [
                        {"$ne": [{"$ifNull": ["$quota_period", ""]}, period]},
                        1,
                        {"$add": [{"$ifNull": ["$monthly_project_count", 0]}, 1]},
                    ]
                },
                "quota_period": period,
                "updated_at": now,
            }
        }
    ]
    user = await db.users.find_one_and_update(
        query,
        update,
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if user:
        return user

    current = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "monthly_project_limit": 1, "monthly_project_count": 1},
    )
    if not current:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "auth.user_not_found",
                    "message": "User no longer exists",
                }
            },
        )

    limit = int(current.get("monthly_project_limit", 3))
    raise HTTPException(
        status_code=402,
        detail={
            "error": {
                "code": "quota.exceeded",
                "message": f"Monthly project limit of {limit} reached",
                "limit": limit,
                "period": period,
            }
        },
    )


async def release_project_slot(user_id: str) -> None:
    """Best-effort rollback when project persistence fails after quota consumption."""
    await get_db().users.update_one(
        {
            "id": user_id,
            "quota_period": quota_period(),
            "monthly_project_count": {"$gt": 0},
        },
        {
            "$inc": {"monthly_project_count": -1},
            "$set": {"updated_at": utc_now()},
        },
    )
