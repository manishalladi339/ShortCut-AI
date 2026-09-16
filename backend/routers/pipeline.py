"""Durable Create For Me request and status endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError
from core.config import settings
from core.deps import get_current_user
from db.mongo import get_db
from models.ai_plan import CreateAIEditPlanRequest
from models.job import JobType, JobOut
from routers.project_state import _get_or_create_state
from services import job_service

router = APIRouter(prefix="/projects", tags=["pipeline"])


@router.post("/{project_id}/pipeline", response_model=JobOut, status_code=202)
async def start_pipeline(
    project_id: str,
    body: CreateAIEditPlanRequest,
    user: dict = Depends(get_current_user),
):
    state = await _get_or_create_state(project_id, user["id"])
    existing = await get_db().jobs.find_one(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "type": "create_for_me",
            "status": {"$in": ["queued", "running"]},
        },
        {"_id": 0},
    )
    if existing:
        return JobOut(**existing)
    sequence = next(
        s for s in state["sequences"] if s["id"] == state["active_sequence_id"]
    )
    if any(t["clips"] for t in sequence["tracks"]):
        raise HTTPException(
            status_code=409,
            detail="Timeline already has edits. Use an AI proposal to review changes.",
        )
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI processing is not configured. Configure the AI provider before starting.",
        )
    if not await get_db().assets.count_documents(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "kind": "video",
            "upload_status": "uploaded",
        }
    ):
        raise HTTPException(status_code=422, detail="Upload at least one video first")
    try:
        job = await job_service.enqueue(
            user_id=user["id"],
            project_id=project_id,
            job_type=JobType.create_for_me,
            payload={
                "request": body.model_dump(),
                "expected_version": state["version"],
            },
            max_attempts=1,
        )
    except DuplicateKeyError:
        job = await get_db().jobs.find_one(
            {
                "project_id": project_id,
                "user_id": user["id"],
                "type": "create_for_me",
                "status": {"$in": ["queued", "running"]},
            },
            {"_id": 0},
        )
    return JobOut(**job)


@router.get("/{project_id}/pipeline", response_model=JobOut | None)
async def pipeline_status(project_id: str, user: dict = Depends(get_current_user)):
    doc = await get_db().jobs.find_one(
        {"project_id": project_id, "user_id": user["id"], "type": "create_for_me"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return JobOut(**doc) if doc else None
