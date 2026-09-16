"""Server-owned orchestration: media preparation -> analysis -> plan -> apply -> export.

All child jobs are durable. App disconnection does not stop the pipeline.
"""

import asyncio
import logging
import time
from fastapi import HTTPException
from core.config import settings
from core.security import utc_now
from db.mongo import get_db
from models.ai_plan import CreateAIEditPlanRequest, ApplyAIEditPlanRequest
from models.export import ExportRequest
from models.job import JobType
from routers.ai_planner import create_ai_edit_plan, apply_ai_edit_plan
from routers.intelligence import analyze_asset
from routers.render import create_export
from services import job_service

logger = logging.getLogger(__name__)


async def wait_for_job(job_id: str, parent: dict, progress: int):
    deadline = time.monotonic() + 7200
    while time.monotonic() < deadline:
        job = await get_db().jobs.find_one(
            {"id": job_id, "user_id": parent["user_id"]}, {"_id": 0}
        )
        if not job:
            raise RuntimeError("A required processing job no longer exists")
        if job["status"] == "succeeded":
            return job
        if job["status"] == "failed":
            raise RuntimeError(job.get("error_message") or "A processing stage failed")
        await job_service.set_progress(parent["id"], progress)
        await asyncio.sleep(2)
    raise RuntimeError("Processing timed out. Check the worker services and retry.")


async def process_one():
    job = await job_service.claim_next(JobType.create_for_me)
    if not job:
        return False
    db = get_db()
    try:
        user = await db.users.find_one({"id": job["user_id"]}, {"_id": 0})
        project_id = job["project_id"]
        if not user:
            raise RuntimeError("Account no longer exists")
        assets = await db.assets.find(
            {
                "project_id": project_id,
                "user_id": job["user_id"],
                "kind": "video",
                "upload_status": "uploaded",
            },
            {"_id": 0},
        ).to_list(100)
        if not assets:
            raise RuntimeError("No uploaded video remains")
        for index, asset in enumerate(assets):
            progress = 10 + int(45 * index / len(assets))
            if asset.get("processing_status") != "ready":
                if not asset.get("processing_job_id"):
                    raise RuntimeError("Media upload has not been confirmed")
                await wait_for_job(asset["processing_job_id"], job, progress)
            previous = await db.media_intelligence.find_one(
                {
                    "asset_id": asset["id"],
                    "user_id": job["user_id"],
                    "status": "completed",
                    "embedding_model": settings.EMBEDDING_MODEL,
                }
            )
            if not previous:
                analysis = await analyze_asset(asset["id"], user)
                await wait_for_job(analysis.job_id, job, progress)
        await job_service.set_progress(job["id"], 60)
        current = await db.project_states.find_one(
            {"project_id": project_id, "user_id": job["user_id"]}, {"_id": 0}
        )
        if not current or current["version"] != job["payload"]["expected_version"]:
            raise RuntimeError(
                "Timeline changed during analysis. Review an AI proposal to continue without overwriting your edits."
            )
        plan = await create_ai_edit_plan(
            project_id, CreateAIEditPlanRequest(**job["payload"]["request"]), user
        )
        await db.jobs.update_one(
            {"id": job["id"]}, {"$set": {"result.plan_id": plan.id}}
        )
        await apply_ai_edit_plan(
            project_id,
            plan.id,
            ApplyAIEditPlanRequest(expected_version=job["payload"]["expected_version"]),
            user,
        )
        await job_service.set_progress(job["id"], 75)
        export = await create_export(project_id, ExportRequest(preset="source"), user)
        await db.jobs.update_one(
            {"id": job["id"]}, {"$set": {"result.export_id": export.id}}
        )
        await wait_for_job(export.job_id, job, 85)
        await job_service.succeed(
            job["id"], {"plan_id": plan.id, "export_id": export.id}
        )
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"status": "completed", "updated_at": utc_now()}},
        )
    except Exception as exc:
        message = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
        await job_service.fail(job, code="pipeline.failed", message=message)
        logger.exception("Pipeline failed: %s", job["id"])
    return True


async def main():
    while True:
        if not await process_one():
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SEC)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
