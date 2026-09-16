"""Render-plan and export API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

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


def export_updates_from_job(doc: dict, job: dict, *, now=None) -> dict:
    """Pure reconciliation policy used by API reads and unit tests."""
    fallback_now = now or utc_now()
    if job.get("status") == "succeeded":
        result = job.get("result") or {}
        if (
            result.get("export_id") == doc.get("id")
            and result.get("storage_key")
        ):
            return {
                "status": "completed",
                "active": False,
                "storage_key": result.get("storage_key"),
                "duration_sec": result.get("duration_sec"),
                "render_metadata": result.get("render_metadata") or {},
                "qa_status": result.get("qa_status"),
                "qa_report": result.get("qa_report"),
                "updated_at": job.get("finished_at") or job.get("updated_at") or fallback_now,
            }
    if job.get("status") == "failed" and doc.get("status") != "completed":
        return {
            "status": "failed",
            "active": False,
            "updated_at": job.get("finished_at") or job.get("updated_at") or fallback_now,
        }
    if job.get("status") == "queued" and doc.get("status") == "rendering":
        return {
            "status": "queued",
            "active": True,
            "updated_at": job.get("updated_at") or fallback_now,
        }
    return {}


async def _reconcile_export_from_job(doc: dict) -> dict:
    """Repair an export record from its durable job result/status when needed."""
    if doc.get("status") == "completed" and doc.get("storage_key"):
        return doc

    job_id = doc.get("job_id")
    if not job_id:
        return doc

    job = await get_db().jobs.find_one(
        {
            "id": job_id,
            "user_id": doc.get("user_id"),
        },
        {"_id": 0},
    )
    if not job:
        return doc

    updates = export_updates_from_job(doc, job)
    if not updates:
        return doc

    await get_db().exports.update_one(
        {
            "id": doc["id"],
            "user_id": doc["user_id"],
            "status": {"$ne": "completed"},
        },
        {"$set": updates},
    )
    return {**doc, **updates}


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
    if not plan.clips:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "render.empty_sequence", "message": "Sequence has no renderable clips"}},
        )

    db = get_db()

    # Repeated taps must not enqueue duplicate expensive renders for the exact
    # same canonical timeline version.
    existing = await db.exports.find_one(
        {
            "user_id": user["id"],
            "project_id": project_id,
            "sequence_id": plan.sequence_id,
            "project_state_version": plan.project_state_version,
            "preset": body.preset,
            "status": {"$in": ["queued", "rendering"]},
        },
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if existing:
        existing = await _reconcile_export_from_job(existing)
        return _export_out(existing)

    now = utc_now()
    export_id = str(uuid.uuid4())
    job = await job_service.enqueue(
        user_id=user["id"],
        project_id=project_id,
        job_type=JobType.render_export,
        payload={
            "export_id": export_id,
            "preset": body.preset,
            "render_plan": plan.model_dump(mode="json"),
        },
        max_attempts=2,
    )
    doc = {
        "id": export_id,
        "user_id": user["id"],
        "project_id": project_id,
        "sequence_id": plan.sequence_id,
        "project_state_version": plan.project_state_version,
        "status": "queued",
        "active": True,
        "preset": body.preset,
        "job_id": job["id"],
        "storage_key": None,
        "duration_sec": None,
        "render_metadata": {},
        "qa_status": None,
        "qa_report": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.exports.insert_one(doc)
    except DuplicateKeyError:
        # Another request won the active-export unique index after our initial
        # read. Remove our still-unclaimed orphan job when possible and return
        # the winning export instead of surfacing a 500.
        await db.jobs.delete_one(
            {
                "id": job["id"],
                "status": "queued",
                "attempt": 0,
            }
        )
        existing = await db.exports.find_one(
            {
                "user_id": user["id"],
                "project_id": project_id,
                "sequence_id": plan.sequence_id,
                "project_state_version": plan.project_state_version,
                "preset": body.preset,
                "status": {"$in": ["queued", "rendering"]},
            },
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if existing:
            existing = await _reconcile_export_from_job(existing)
            return _export_out(existing)
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "render.request_race",
                    "message": "Another render request changed state; retry the export.",
                }
            },
        )
    return _export_out(doc)


@router.get("/{project_id}/exports", response_model=list[ExportOut])
async def list_exports(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> list[ExportOut]:
    docs = await (
        get_db().exports.find(
            {"project_id": project_id, "user_id": user["id"]}, {"_id": 0}
        )
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    reconciled = [await _reconcile_export_from_job(doc) for doc in docs]
    return [_export_out(doc) for doc in reconciled]


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
            detail={"error": {"code": "resource.not_found", "message": "Export not found"}},
        )
    doc = await _reconcile_export_from_job(doc)
    return _export_out(doc)
