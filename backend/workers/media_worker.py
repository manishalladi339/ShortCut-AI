"""Media-ingestion worker.

Run one iteration:
    python -m workers.media_worker --once

Run continuously:
    python -m workers.media_worker
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from core.security import utc_now
from db.mongo import close as close_mongo
from db.mongo import get_db
from models.job import JobType
from services import job_service
from services.media_probe import MediaProbeError, probe
from services.storage import materialize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut.media-worker")


async def process_one() -> bool:
    job = await job_service.claim_next(JobType.media_probe)
    if not job:
        return False

    try:
        db = get_db()
        asset = await db.assets.find_one({"id": job["asset_id"]}, {"_id": 0})
        if not asset:
            raise RuntimeError("asset no longer exists")

        await job_service.set_progress(job["id"], 20)
        suffix = Path(asset["filename"]).suffix
        with materialize(asset["storage_key"], suffix=suffix) as local_path:
            metadata = probe(local_path)

        await job_service.set_progress(job["id"], 80)
        update = {
            "processing_status": "ready",
            "processing_job_id": job["id"],
            "media_metadata": metadata,
            "duration_sec": metadata.get("duration_sec"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "updated_at": utc_now(),
        }
        await db.assets.update_one({"id": asset["id"]}, {"$set": update})
        await job_service.succeed(job["id"], metadata)
        logger.info("processed asset %s", asset["id"])
        return True
    except MediaProbeError as exc:
        await job_service.fail(job, code="media.probe_failed", message=str(exc))
        logger.warning("media probe failed for job %s: %s", job["id"], exc)
        return True
    except Exception as exc:
        await job_service.fail(job, code="media.processing_failed", message=str(exc))
        logger.exception("media processing failed for job %s", job["id"])
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
