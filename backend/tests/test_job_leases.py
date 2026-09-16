"""Tests for durable job-lease policy and public job schema."""
from datetime import datetime, timezone

from models.job import JobOut
from services.job_service import recovery_status


def _job(*, attempt: int, max_attempts: int) -> dict:
    return {
        "attempt": attempt,
        "max_attempts": max_attempts,
    }


def test_stale_job_requeues_while_retry_budget_remains():
    assert recovery_status(_job(attempt=1, max_attempts=3)) == "queued"
    assert recovery_status(_job(attempt=2, max_attempts=3)) == "queued"


def test_stale_job_fails_when_retry_budget_is_exhausted():
    assert recovery_status(_job(attempt=3, max_attempts=3)) == "failed"


def test_public_job_schema_exposes_lease_health_but_not_token():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    job = JobOut(
        id="job-1",
        user_id="user-1",
        type="render_export",
        status="running",
        progress=42,
        attempt=1,
        max_attempts=2,
        error_code=None,
        error_message=None,
        result={},
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=None,
        heartbeat_at=now,
        lease_expires_at=now,
        lease_token="secret-worker-token",
    )
    public = job.model_dump()
    assert public["heartbeat_at"] == now
    assert public["lease_expires_at"] == now
    assert "lease_token" not in public
