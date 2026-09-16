"""Render-plan and export API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.export import ExportOut, ExportRequest
from models.job import JobType
from models.render_plan import RenderPlan
from services import job_service
from services.render_plan import compile_render_plan
from services.storage import get_storage

router = APIRouter(prefix="/projects", tags=["render"])


def _export_out(doc: dict) -> ExportOut:
    download_url = None
    if doc.get("storage_key") and doc.get("status") == "completed":
        download_url = get_storage().presign_download(doc["storage_key"])
    return ExportOut(**{**doc, "download_url": download_url})


@router.post("/{project_id}/render-plan", response_model=RenderPlan)
async def create_render_plan(
    project_id: str,
    sequence_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> RenderPlan:
    return await compile_render_plan(
        project_id=project_id,
        user_id=user["id"],
        sequence_id=sequence_id,
    )


@router.post(
    "/{project_id}/exports",
    response_model=ExportOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_export(
    project_id: str,
    body: ExportRequest,
    user: dict = Depends(get_current_user),
) -> ExportOut:
    plan = await compile_render_plan(
        project_id=project_id,
        user_id=user["id"],
        sequence_id=body.sequence_id,
    )
    plan.watermark = user.get("subscription_tier", "free") == "free"
    if body.preset == "vertical_1080p":
        plan.width, plan.height = 1080, 1920
    if not plan.clips:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "render.empty_sequence",
                    "message": "Sequence has no renderable clips",
                }
            },
        )

    duration = plan.duration_ticks * plan.timebase_denominator / plan.timebase_numerator
    if duration > 300 or len(plan.clips) > 100:
        raise HTTPException(
            status_code=422, detail="Exports support at most 5 minutes and 100 clips"
        )
    if plan.width % 2 or plan.height % 2 or plan.width * plan.height > 3840 * 2160:
        raise HTTPException(
            status_code=422, detail="Use even frame dimensions up to 4K"
        )
    db = get_db()
    now = utc_now()
    export_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    async def enqueue_export():
        return await job_service.enqueue(
            user_id=user["id"],
            project_id=project_id,
            job_type=JobType.render_export,
            payload={
                "export_id": export_id,
                "preset": body.preset,
                "render_plan": plan.model_dump(mode="json"),
            },
            max_attempts=2,
            job_id=job_id,
        )

    doc = {
        "id": export_id,
        "user_id": user["id"],
        "project_id": project_id,
        "sequence_id": plan.sequence_id,
        "project_state_version": plan.project_state_version,
        "status": "queued",
        "preset": body.preset,
        "job_id": job_id,
        "storage_key": None,
        "duration_sec": None,
        "render_metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    await db.exports.insert_one(doc)
    await enqueue_export()
    return _export_out(doc)


@router.get("/{project_id}/exports", response_model=list[ExportOut])
async def list_exports(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> list[ExportOut]:
    docs = await (
        get_db()
        .exports.find({"project_id": project_id, "user_id": user["id"]}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return [_export_out(doc) for doc in docs]


@router.get("/{project_id}/exports/{export_id}", response_model=ExportOut)
async def get_export(
    project_id: str,
    export_id: str,
    user: dict = Depends(get_current_user),
) -> ExportOut:
    doc = await get_db().exports.find_one(
        {"id": export_id, "project_id": project_id, "user_id": user["id"]},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "resource.not_found", "message": "Export not found"}
            },
        )
    return _export_out(doc)
