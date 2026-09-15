"""Authenticated processing-job API."""
from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import get_current_user
from db.mongo import get_db
from models.job import JobOut, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: JobStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> list[JobOut]:
    query: dict = {"user_id": user["id"]}
    if status is not None:
        query["status"] = status.value
    docs = await (
        get_db().jobs.find(query, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return [JobOut(**doc) for doc in docs]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: dict = Depends(get_current_user)) -> JobOut:
    doc = await get_db().jobs.find_one(
        {"id": job_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Job not found"}},
        )
    return JobOut(**doc)
