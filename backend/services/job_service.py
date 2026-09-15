"""Mongo-backed job queue primitives."""
from __future__ import annotations

import uuid
from typing import Any

from pymongo import ReturnDocument

from core.security import utc_now
from db.mongo import get_db
from models.job import JobStatus, JobType


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
    }
    await get_db().jobs.insert_one(doc)
    return doc


async def claim_next(job_type: JobType) -> dict | None:
    now = utc_now()
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
                "progress": 5,
            },
            "$inc": {"attempt": 1},
        },
        sort=[("created_at", 1)],
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )


async def set_progress(job_id: str, progress: int) -> None:
    await get_db().jobs.update_one(
        {"id": job_id, "status": JobStatus.running.value},
        {"$set": {"progress": max(0, min(100, progress)), "updated_at": utc_now()}},
    )


async def succeed(job_id: str, result: dict) -> None:
    now = utc_now()
    await get_db().jobs.update_one(
        {"id": job_id},
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


async def fail(job: dict, *, code: str, message: str) -> None:
    now = utc_now()
    retryable = job["attempt"] < job["max_attempts"]
    await get_db().jobs.update_one(
        {"id": job["id"]},
        {
            "$set": {
                "status": JobStatus.queued.value if retryable else JobStatus.failed.value,
                "progress": 0 if retryable else job.get("progress", 0),
                "error_code": code,
                "error_message": message[:4000],
                "finished_at": None if retryable else now,
                "updated_at": now,
            }
        },
    )
