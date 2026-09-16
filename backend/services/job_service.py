"""Mongo-backed job queue primitives."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import timedelta
from typing import Any

from pymongo import ReturnDocument

from core.security import utc_now
from db.mongo import get_db
from models.job import JobStatus, JobType

_claims: ContextVar[dict] = ContextVar("job_claims", default={})
LEASE_SECONDS = 3600


class LostLeaseError(RuntimeError):
    pass


def _owned_claim(job_id: str) -> dict:
    token = _claims.get().get(job_id)
    return {
        "id": job_id,
        "status": "running",
        "lease_token": token,
        "lease_expires_at": {"$gt": utc_now()},
    }


async def assert_claim(job: dict) -> None:
    owned = await get_db().jobs.find_one(
        {
            "id": job["id"],
            "status": "running",
            "lease_token": job.get("lease_token"),
            "lease_expires_at": {"$gt": utc_now()},
        },
        {"id": 1},
    )
    if not owned:
        raise LostLeaseError(
            "Processing lease was lost; another worker may have recovered this job"
        )


async def recover_stalled(job_type: JobType) -> None:
    now = utc_now()
    stale = {
        "type": job_type.value,
        "status": "running",
        "lease_expires_at": {"$lt": now},
    }
    await get_db().jobs.update_many(
        {**stale, "$expr": {"$lt": ["$attempt", "$max_attempts"]}},
        {
            "$set": {
                "status": "queued",
                "updated_at": now,
                "error_code": "worker.interrupted",
                "error_message": "Worker interrupted; retrying",
                "lease_token": None,
            }
        },
    )
    failed = await get_db().jobs.find(stale, {"_id": 0}).to_list(1000)
    for job in failed:
        result = await get_db().jobs.update_one(
            {**stale, "id": job["id"]},
            {
                "$set": {
                    "status": "failed",
                    "updated_at": now,
                    "finished_at": now,
                    "error_code": "worker.interrupted",
                    "error_message": "Worker interrupted. Retry the operation.",
                }
            },
        )
        if not result.modified_count:
            continue
        if job_type == JobType.render_export:
            await get_db().exports.update_one(
                {"job_id": job["id"]}, {"$set": {"status": "failed", "updated_at": now}}
            )
        elif job_type == JobType.media_intelligence:
            await get_db().media_intelligence.update_one(
                {"job_id": job["id"]}, {"$set": {"status": "failed", "updated_at": now}}
            )
        elif job_type == JobType.media_probe:
            await get_db().assets.update_one(
                {"processing_job_id": job["id"]},
                {"$set": {"processing_status": "failed", "updated_at": now}},
            )


async def enqueue(
    *,
    user_id: str,
    job_type: JobType,
    project_id: str | None = None,
    asset_id: str | None = None,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
    job_id: str | None = None,
) -> dict:
    now = utc_now()
    doc = {
        "id": job_id or str(uuid.uuid4()),
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
    }
    await get_db().jobs.update_one(
        {"id": doc["id"]}, {"$setOnInsert": doc}, upsert=True
    )
    return doc


async def claim_next(job_type: JobType) -> dict | None:
    await recover_stalled(job_type)
    now = utc_now()
    token = str(uuid.uuid4())
    job = await get_db().jobs.find_one_and_update(
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
                "progress": 5,
                "lease_token": token,
                "lease_expires_at": now + timedelta(seconds=LEASE_SECONDS),
            },
            "$inc": {"attempt": 1},
        },
        sort=[("created_at", 1)],
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )

    if job:
        _claims.set({**_claims.get(), job["id"]: token})
    return job


async def set_progress(job_id: str, progress: int) -> None:
    result = await get_db().jobs.update_one(
        _owned_claim(job_id),
        {
            "$set": {
                "progress": max(0, min(100, progress)),
                "updated_at": utc_now(),
                "lease_expires_at": utc_now() + timedelta(seconds=LEASE_SECONDS),
            }
        },
    )
    if not result.matched_count:
        raise LostLeaseError("Processing lease expired")


async def succeed(job_id: str, result: dict) -> None:
    now = utc_now()
    await get_db().jobs.update_one(
        _owned_claim(job_id),
        {
            "$set": {
                "status": JobStatus.succeeded.value,
                "progress": 100,
                "result": result,
                "error_code": None,
                "error_message": None,
                "finished_at": now,
                "updated_at": now,
            }
        },
    )


async def fail(job: dict, *, code: str, message: str) -> bool:
    now = utc_now()
    retryable = job["attempt"] < job["max_attempts"]
    result = await get_db().jobs.update_one(
        {"id": job["id"], "status": "running", "lease_token": job.get("lease_token")},
        {
            "$set": {
                "status": (
                    JobStatus.queued.value if retryable else JobStatus.failed.value
                ),
                "progress": 0 if retryable else job.get("progress", 0),
                "error_code": code,
                "error_message": message[:4000],
                "finished_at": None if retryable else now,
                "updated_at": now,
            }
        },
    )

    return bool(result.matched_count)
