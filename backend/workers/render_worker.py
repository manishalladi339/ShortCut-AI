"""Render worker for queued export jobs with durable lease ownership."""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import settings
from core.security import utc_now
from db.mongo import close as close_mongo
from db.mongo import get_db
from models.job import JobStatus, JobType
from models.render_plan import RenderPlan
from services import job_service
from services.export_qa import analyze_export
from services.media_probe import probe
from services.render_executor import execute
from services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut.render-worker")


def _worker_lease_seconds() -> int:
    return max(settings.JOB_LEASE_SECONDS, settings.RENDER_TIMEOUT_SEC + 300)


async def _recover_stale_exports() -> None:
    recovered = await job_service.recover_stale_jobs(JobType.render_export)
    if not recovered:
        return
    db = get_db()
    for job in recovered:
        export_id = (job.get("payload") or {}).get("export_id")
        if not export_id:
            continue
        export_status = (
            "queued"
            if job["recovered_status"] == JobStatus.queued.value
            else "failed"
        )
        await db.exports.update_one(
            {
                "id": export_id,
                "status": {"$ne": "completed"},
            },
            {
                "$set": {
                    "status": export_status,
                    "active": export_status in {"queued", "rendering"},
                    "updated_at": utc_now(),
                }
            },
        )
        logger.warning(
            "recovered stale render job %s -> %s",
            job["id"],
            job["recovered_status"],
        )


async def _progress(job: dict, progress: int) -> None:
    ok = await job_service.set_progress(
        job["id"],
        progress,
        lease_token=job["lease_token"],
        lease_seconds=_worker_lease_seconds(),
    )
    if not ok:
        raise RuntimeError("render job lease was lost")


async def _complete_already_rendered(job: dict, export: dict) -> bool:
    if export.get("status") != "completed" or not export.get("storage_key"):
        return False
    result = {
        "export_id": export["id"],
        "storage_key": export["storage_key"],
        "duration_sec": export.get("duration_sec"),
        "render_metadata": export.get("render_metadata") or {},
        "qa_status": export.get("qa_status"),
        "qa_report": export.get("qa_report"),
        "reconciled_existing_export": True,
    }
    ok = await job_service.succeed(
        job["id"],
        result,
        lease_token=job["lease_token"],
    )
    if not ok:
        logger.warning("lost lease while reconciling completed export %s", export["id"])
    return True


async def process_one() -> bool:
    await _recover_stale_exports()
    job = await job_service.claim_next(
        JobType.render_export,
        lease_seconds=_worker_lease_seconds(),
    )
    if not job:
        return False

    db = get_db()
    export_id = job.get("payload", {}).get("export_id")
    try:
        export = await db.exports.find_one({"id": export_id}, {"_id": 0})
        if not export:
            raise RuntimeError("export record not found")

        if await _complete_already_rendered(job, export):
            return True

        await db.exports.update_one(
            {
                "id": export_id,
                "status": {"$ne": "completed"},
            },
            {
                "$set": {
                    "status": "rendering",
                    "active": True,
                    "updated_at": utc_now(),
                }
            },
        )
        await _progress(job, 10)

        plan = RenderPlan(**job["payload"]["render_plan"])
        with TemporaryDirectory(prefix="shortcut-export-") as tmp:
            output = Path(tmp) / "output.mp4"
            result = execute(plan, output)
            await _progress(job, 75)

            metadata = probe(output)
            expected_duration = (
                plan.duration_ticks
                * plan.timebase_denominator
                / plan.timebase_numerator
            )
            actual_duration = float(metadata.get("duration_sec") or 0.0)
            if actual_duration <= 0:
                raise RuntimeError("render QC failed: output duration is missing")
            tolerance = max(0.35, expected_duration * 0.03)
            if abs(actual_duration - expected_duration) > tolerance:
                raise RuntimeError(
                    "render QC failed: duration mismatch "
                    f"(expected {expected_duration:.3f}s, got {actual_duration:.3f}s)"
                )
            if metadata.get("width") != plan.width or metadata.get("height") != plan.height:
                raise RuntimeError(
                    "render QC failed: frame size mismatch "
                    f"(expected {plan.width}x{plan.height}, "
                    f"got {metadata.get('width')}x{metadata.get('height')})"
                )
            if not metadata.get("video_codec"):
                raise RuntimeError("render QC failed: output has no video stream")

            await _progress(job, 82)
            qa_report = analyze_export(output, plan)
            await _progress(job, 90)

            if not await job_service.lease_active(
                job["id"],
                lease_token=job["lease_token"],
            ):
                raise RuntimeError("render job lease expired before upload")

            storage_key = (
                f"users/{job['user_id']}/exports/{job['project_id']}/"
                f"{export_id}.mp4"
            )
            # The key is deterministic, so a retry safely overwrites a partial/
            # orphaned upload produced by a crashed previous attempt.
            get_storage().upload_file(
                storage_key,
                output,
                content_type="video/mp4",
            )
            # Fence completion after the potentially slow upload. If the lease
            # expired, this attempt must not commit export/job state.
            await _progress(job, 95)

        duration_sec = float(metadata.get("duration_sec") or result["duration_sec"])
        now = utc_now()
        job_result = {
            "export_id": export_id,
            "storage_key": storage_key,
            "duration_sec": duration_sec,
            "render_metadata": metadata,
            "qa_status": qa_report.get("status"),
            "qa_report": qa_report,
            **result,
        }

        # Commit the durable job result first. If the process dies immediately
        # after this line, export reads reconcile from this result.
        owned = await job_service.succeed(
            job["id"],
            job_result,
            lease_token=job["lease_token"],
        )
        if not owned:
            logger.warning(
                "render attempt %s lost ownership before completion; ignoring result",
                job["id"],
            )
            return True

        await db.exports.update_one(
            {
                "id": export_id,
                "status": {"$ne": "completed"},
            },
            {
                "$set": {
                    "status": "completed",
                    "active": False,
                    "storage_key": storage_key,
                    "duration_sec": duration_sec,
                    "render_metadata": metadata,
                    "qa_status": qa_report.get("status"),
                    "qa_report": qa_report,
                    "updated_at": now,
                }
            },
        )
        return True

    except Exception as exc:
        final = int(job["attempt"]) >= int(job["max_attempts"])
        owned = await job_service.fail(
            job,
            code="render.failed",
            message=str(exc),
            lease_token=job.get("lease_token"),
        )
        if owned and export_id:
            await db.exports.update_one(
                {
                    "id": export_id,
                    "status": {"$ne": "completed"},
                },
                {
                    "$set": {
                        "status": "failed" if final else "queued",
                        "active": not final,
                        "updated_at": utc_now(),
                    }
                },
            )
        elif not owned:
            logger.warning(
                "render worker lost lease for job %s; stale attempt will not mutate export",
                job["id"],
            )
        logger.exception("render failed for job %s", job["id"])
        return True


async def run_forever() -> None:
    while True:
        did_work = await process_one()
        if not did_work:
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SEC)


async def _main(once: bool) -> None:
    try:
        if once:
            await process_one()
        else:
            await run_forever()
    finally:
        await close_mongo()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.once))
