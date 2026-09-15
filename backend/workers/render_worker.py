"""Render worker for queued export jobs."""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from core.security import utc_now
from db.mongo import close as close_mongo
from db.mongo import get_db
from models.job import JobType
from models.render_plan import RenderPlan
from services import job_service
from services.media_probe import probe
from services.render_executor import execute
from services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut.render-worker")


async def process_one() -> bool:
    job = await job_service.claim_next(JobType.render_export)
    if not job:
        return False

    db = get_db()
    export_id = job.get("payload", {}).get("export_id")
    try:
        export = await db.exports.find_one({"id": export_id}, {"_id": 0})
        if not export:
            raise RuntimeError("export record not found")

        await db.exports.update_one(
            {"id": export_id},
            {"$set": {"status": "rendering", "updated_at": utc_now()}},
        )
        await job_service.set_progress(job["id"], 10)

        plan = RenderPlan(**job["payload"]["render_plan"])
        with TemporaryDirectory(prefix="shortcut-export-") as tmp:
            output = Path(tmp) / "output.mp4"
            result = execute(plan, output)
            await job_service.set_progress(job["id"], 75)

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

            await job_service.set_progress(job["id"], 90)

            storage_key = (
                f"users/{job['user_id']}/exports/{job['project_id']}/"
                f"{export_id}.mp4"
            )
            get_storage().upload_file(
                storage_key, output, content_type="video/mp4"
            )

        duration_sec = float(metadata.get("duration_sec") or result["duration_sec"])
        now = utc_now()
        await db.exports.update_one(
            {"id": export_id},
            {
                "$set": {
                    "status": "completed",
                    "storage_key": storage_key,
                    "duration_sec": duration_sec,
                    "render_metadata": metadata,
                    "updated_at": now,
                }
            },
        )
        await job_service.succeed(
            job["id"],
            {
                "export_id": export_id,
                "storage_key": storage_key,
                "duration_sec": duration_sec,
                "render_metadata": metadata,
                **result,
            },
        )
        return True

    except Exception as exc:
        final = job["attempt"] >= job["max_attempts"]
        await job_service.fail(job, code="render.failed", message=str(exc))
        if export_id:
            await db.exports.update_one(
                {"id": export_id},
                {
                    "$set": {
                        "status": "failed" if final else "queued",
                        "updated_at": utc_now(),
                    }
                },
            )
        logger.exception("render failed for job %s", job["id"])
        return True


async def run_forever() -> None:
    from core.config import settings

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
