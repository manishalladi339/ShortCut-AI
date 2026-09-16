"""Mongo-backed durable job queue primitives with lease fencing."""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from pymongo import ReturnDocument

from core.config import settings
from core.security import utc_now
from db.mongo import get_db
from models.job import JobStatus, JobType
from services.job_policy import recovery_status


def _lease_seconds(value: int | None = None) -> int:
    return max(30, int(value or settings.JOB_LEASE_SECONDS))


def _lease_deadline(now, value: int | None = None):
    return now + timedelta(seconds=_lease_seconds(value))


def _running_owner_query(
    *,
    job_id: str,
    lease_token: str | None,
    require_unexpired: bool = True,
) -> dict:
    query: dict[str, Any] = {
        "id": job_id,
        "status": JobStatus.running.value,
    }
    if lease_token is not None:
        query["lease_token"] = lease_token
        if require_unexpired:
            query["lease_expires_at"] = {"$gt": utc_now()}
    return query


async def enqueue(
    *,
    user_id: str,
    job_type: JobType,
    project_id: str | None = None,
    asset_id: str | None = None,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> dict:
    now = utc_now()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "project_id": project_id,
        "asset_id": asset_id,
        "type": job_type.value,
        "status": JobStatus.queued.value,
        "progress": 0,
        "attempt": 0,
        "max_attempts": max_attempts,
        "payload": payload or {},
        "error_code": None,
        "error_message": None,
        "result": {},
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }
    await get_db().jobs.insert_one(doc)
    return doc


async def claim_next(
    job_type: JobType,
    *,
    lease_seconds: int | None = None,
) -> dict | None:
    now = utc_now()
    token = str(uuid.uuid4())
    return await get_db().jobs.find_one_and_update(
        {
            "type": job_type.value,
            "status": JobStatus.queued.value,
            "$expr": {"$lt": ["$attempt", "$max_attempts"]},
        },
        {
            "$set": {
                "status": JobStatus.running.value,
                "started_at": now,
                "updated_at": now,
                "heartbeat_at": now,
                "lease_token": token,
                "lease_expires_at": _lease_deadline(now, lease_seconds),
                "progress": 5,
                "finished_at": None,
            },
            "$inc": {"attempt": 1},
        },
        sort=[("created_at", 1)],
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )


async def heartbeat(
    job_id: str,
    *,
    lease_token: str,
    lease_seconds: int | None = None,
) -> bool:
    now = utc_now()
    result = await get_db().jobs.update_one(
        _running_owner_query(
            job_id=job_id,
            lease_token=lease_token,
            require_unexpired=True,
        ),
        {
            "$set": {
                "heartbeat_at": now,
                "lease_expires_at": _lease_deadline(now, lease_seconds),
                "updated_at": now,
            }
        },
    )
    return result.modified_count == 1


async def lease_active(job_id: str, *, lease_token: str) -> bool:
    doc = await get_db().jobs.find_one(
        _running_owner_query(
            job_id=job_id,
            lease_token=lease_token,
            require_unexpired=True,
        ),
        {"_id": 0, "id": 1},
    )
    return bool(doc)


async def set_progress(
    job_id: str,
    progress: int,
    *,
    lease_token: str | None = None,
    lease_seconds: int | None = None,
) -> bool:
    now = utc_now()
    updates: dict[str, Any] = {
        "progress": max(0, min(100, progress)),
        "updated_at": now,
    }
    if lease_token is not None:
        updates["heartbeat_at"] = now
        updates["lease_expires_at"] = _lease_deadline(now, lease_seconds)

    result = await get_db().jobs.update_one(
        _running_owner_query(
            job_id=job_id,
            lease_token=lease_token,
            require_unexpired=lease_token is not None,
        ),
        {"$set": updates},
    )
    return result.modified_count == 1


async def succeed(
    job_id: str,
    result: dict,
    *,
    lease_token: str | None = None,
) -> bool:
    now = utc_now()
    updated = await get_db().jobs.update_one(
        _running_owner_query(
            job_id=job_id,
            lease_token=lease_token,
            require_unexpired=lease_token is not None,
        ),
        {
            "$set": {
                "status": JobStatus.succeeded.value,
                "progress": 100,
                "result": result,
                "error_code": None,
                "error_message": None,
                "finished_at": now,
                "updated_at": now,
                "heartbeat_at": now if lease_token is not None else None,
                "lease_token": None,
                "lease_expires_at": None,
            }
        },
    )
    return updated.modified_count == 1


async def fail(
    job: dict,
    *,
    code: str,
    message: str,
    lease_token: str | None = None,
) -> bool:
    now = utc_now()
    retryable = int(job["attempt"]) < int(job["max_attempts"])
    next_status = (
        JobStatus.queued.value if retryable else JobStatus.failed.value
    )
    updated = await get_db().jobs.update_one(
        _running_owner_query(
            job_id=job["id"],
            lease_token=lease_token,
            require_unexpired=lease_token is not None,
        ),
        {
            "$set": {
                "status": next_status,
                "progress": 0 if retryable else job.get("progress", 0),
                "error_code": code,
                "error_message": message[:4000],
                "finished_at": None if retryable else now,
                "started_at": None if retryable else job.get("started_at"),
                "updated_at": now,
                "heartbeat_at": None,
                "lease_token": None,
                "lease_expires_at": None,
            }
        },
    )
    return updated.modified_count == 1


async def recover_stale_jobs(
    job_type: JobType | None = None,
    *,
    lease_seconds: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """Requeue/fail jobs whose worker lease expired.

    Legacy running jobs created before leases existed are treated as stale when
    their updated_at is older than one lease interval.
    """
    db = get_db()
    now = utc_now()
    legacy_cutoff = now - timedelta(seconds=_lease_seconds(lease_seconds))

    query: dict[str, Any] = {
        "status": JobStatus.running.value,
        "$or": [
            {"lease_expires_at": {"$lte": now}},
            {
                "lease_expires_at": None,
                "updated_at": {"$lte": legacy_cutoff},
            },
        ],
    }
    if job_type is not None:
        query["type"] = job_type.value

    candidates = await (
        db.jobs.find(query, {"_id": 0})
        .sort("updated_at", 1)
        .limit(max(1, min(500, int(limit))))
        .to_list(max(1, min(500, int(limit))))
    )

    recovered: list[dict] = []
    for job in candidates:
        next_status = recovery_status(job)
        retryable = next_status == JobStatus.queued.value
        token = job.get("lease_token")

        cas: dict[str, Any] = {
            "id": job["id"],
            "status": JobStatus.running.value,
            "lease_token": token,
        }
        if job.get("lease_expires_at") is not None:
            cas["lease_expires_at"] = {"$lte": now}
        else:
            cas["lease_expires_at"] = None
            cas["updated_at"] = {"$lte": legacy_cutoff}

        result = await db.jobs.update_one(
            cas,
            {
                "$set": {
                    "status": next_status,
                    "progress": 0 if retryable else job.get("progress", 0),
                    "error_code": "job.lease_expired",
                    "error_message": (
                        "Worker lease expired before the job completed; "
                        + ("queued for retry." if retryable else "retry budget exhausted.")
                    ),
                    "started_at": None if retryable else job.get("started_at"),
                    "finished_at": None if retryable else now,
                    "updated_at": now,
                    "heartbeat_at": None,
                    "lease_token": None,
                    "lease_expires_at": None,
                }
            },
        )
        if result.modified_count == 1:
            recovered.append(
                {
                    **job,
                    "recovered_status": next_status,
                    "recovered_at": now,
                }
            )
    return recovered
