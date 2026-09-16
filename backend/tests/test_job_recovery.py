"""Recover abandoned worker jobs without accepting stale worker results."""

import asyncio
from datetime import timedelta
import pytest


def test_expired_claim_is_recovered_and_old_worker_is_fenced():
    from core.security import utc_now
    from db import mongo
    from models.job import JobType
    from services import job_service

    mongo._client = None
    mongo._db = None

    async def scenario():
        db = mongo.get_db()
        # Use the pipeline queue, empty outside the dedicated tests.
        job = await job_service.enqueue(
            user_id="lease-test",
            project_id="lease-test",
            job_type=JobType.create_for_me,
            max_attempts=2,
        )
        first = await job_service.claim_next(JobType.create_for_me)
        assert first["id"] == job["id"]
        await db.jobs.update_one(
            {"id": job["id"]},
            {"$set": {"lease_expires_at": utc_now() - timedelta(seconds=1)}},
        )
        second = await job_service.claim_next(JobType.create_for_me)
        assert second["id"] == job["id"] and second["attempt"] == 2
        assert second["lease_token"] != first["lease_token"]
        assert not await job_service.fail(first, code="late", message="old worker")
        with pytest.raises(job_service.LostLeaseError):
            await job_service.assert_claim(first)
        await job_service.set_progress(second["id"], 80)
        await job_service.succeed(second["id"], {"recovered": True})
        assert (await db.jobs.find_one({"id": job["id"]}))["status"] == "succeeded"
        await mongo.close()

    asyncio.run(scenario())
