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
from models.job import JobStatus, JobType
from services import job_service
from services.media_derivatives import MediaDerivativeError, generate as generate_derivatives
from services.media_probe import MediaProbeError, probe
from services.storage import get_storage, materialize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut.media-worker")


def _worker_lease_seconds() -> int:
    return max(
        settings.JOB_LEASE_SECONDS,
        settings.MEDIA_PROBE_TIMEOUT_SEC
        + settings.MEDIA_DERIVATIVE_TIMEOUT_SEC
        + 300,
    )


async def _complete_already_processed(job: dict, asset: dict) -> bool:
    if (
        asset.get("processing_status") != "ready"
        or asset.get("processing_job_id") != job["id"]
    ):
        return False
    owned = await job_service.succeed(
        job["id"],
        {
            "media_metadata": asset.get("media_metadata") or {},
            "derivatives": asset.get("derivatives") or {},
            "reconciled_existing_asset": True,
        },
        lease_token=job["lease_token"],
    )
    if not owned:
        logger.warning("lost lease while reconciling asset %s", asset["id"])
    return True


async def _recover_stale_assets() -> None:
    recovered = await job_service.recover_stale_jobs(JobType.media_probe)
    for job in recovered:
        asset_id = job.get("asset_id")
        if not asset_id:
            continue
        status = (
            "queued"
            if job["recovered_status"] == JobStatus.queued.value
            else "failed"
        )
        await get_db().assets.update_one(
            {
                "id": asset_id,
                "processing_status": {"$ne": "ready"},
            },
            {
                "$set": {
                    "processing_status": status,
                    "updated_at": utc_now(),
                }
            },
        )


async def _progress(job: dict, progress: int) -> None:
    ok = await job_service.set_progress(
        job["id"],
        progress,
        lease_token=job["lease_token"],
        lease_seconds=_worker_lease_seconds(),
    )
    if not ok:
        raise RuntimeError("media job lease was lost")


async def _sync_asset_failure(job: dict, final: bool) -> None:
    await get_db().assets.update_one(
        {"id": job.get("asset_id")},
        {
            "$set": {
                "processing_status": "failed" if final else "queued",
                "updated_at": utc_now(),
            }
        },
    )


async def process_one() -> bool:
    await _recover_stale_assets()
    job = await job_service.claim_next(
        JobType.media_probe,
        lease_seconds=_worker_lease_seconds(),
    )
    if not job:
        return False

    db = get_db()
    try:
        asset = await db.assets.find_one({"id": job["asset_id"]}, {"_id": 0})
        if not asset:
            raise RuntimeError("asset no longer exists")

        if await _complete_already_processed(job, asset):
            return True

        await db.assets.update_one(
            {"id": asset["id"]},
            {"$set": {"processing_status": "processing", "updated_at": utc_now()}},
        )
        await _progress(job, 20)

        suffix = Path(asset["filename"]).suffix
        with materialize(asset["storage_key"], suffix=suffix) as local_path:
            metadata = probe(local_path)
            await _progress(job, 45)
            derivatives = generate_derivatives(
                source_path=local_path,
                asset=asset,
                storage=get_storage(),
            )

        await _progress(job, 80)
        # Extend/fence ownership immediately before durable completion writes.
        await _progress(job, 95)
        await db.assets.update_one(
            {"id": asset["id"]},
            {
                "$set": {
                    "processing_status": "ready",
                    "processing_job_id": job["id"],
                    "media_metadata": metadata,
                    "derivatives": derivatives,
                    "duration_sec": metadata.get("duration_sec"),
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                    "updated_at": utc_now(),
                }
            },
        )
        owned = await job_service.succeed(
            job["id"],
            {"media_metadata": metadata, "derivatives": derivatives},
            lease_token=job["lease_token"],
        )
        if not owned:
            logger.warning("media job %s lost its lease before completion", job["id"])
        logger.info("processed asset %s", asset["id"])
        return True

    except (MediaProbeError, MediaDerivativeError) as exc:
        final = job["attempt"] >= job["max_attempts"]
        owned = await job_service.fail(
            job,
            code="media.probe_failed",
            message=str(exc),
            lease_token=job.get("lease_token"),
        )
        if owned:
            await _sync_asset_failure(job, final)
        logger.warning("media probe failed for job %s: %s", job["id"], exc)
        return True

    except Exception as exc:
        final = job["attempt"] >= job["max_attempts"]
        owned = await job_service.fail(
            job,
            code="media.processing_failed",
            message=str(exc),
            lease_token=job.get("lease_token"),
        )
        if owned:
            await _sync_asset_failure(job, final)
        logger.exception("media processing failed for job %s", job["id"])
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
