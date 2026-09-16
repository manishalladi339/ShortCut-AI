"""Tests for durable export recovery policy."""
from datetime import datetime, timezone

from routers.render import export_updates_from_job


def _export(status="rendering"):
    return {
        "id": "export-1",
        "user_id": "user-1",
        "status": status,
        "job_id": "job-1",
    }


def test_succeeded_job_can_reconstruct_completed_export():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    updates = export_updates_from_job(
        _export(),
        {
            "status": "succeeded",
            "finished_at": now,
            "result": {
                "export_id": "export-1",
                "storage_key": "users/u/exports/p/export-1.mp4",
                "duration_sec": 42.5,
                "render_metadata": {"width": 1080, "height": 1920},
                "qa_status": "warnings",
                "qa_report": {"status": "warnings", "issues": []},
            },
        },
        now=now,
    )
    assert updates["status"] == "completed"
    assert updates["storage_key"].endswith("export-1.mp4")
    assert updates["duration_sec"] == 42.5
    assert updates["qa_status"] == "warnings"
    assert updates["updated_at"] == now


def test_succeeded_job_for_different_export_cannot_reconcile():
    updates = export_updates_from_job(
        _export(),
        {
            "status": "succeeded",
            "result": {
                "export_id": "different-export",
                "storage_key": "somewhere.mp4",
            },
        },
    )
    assert updates == {}


def test_terminal_job_failure_updates_unfinished_export():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    updates = export_updates_from_job(
        _export(),
        {"status": "failed", "finished_at": now, "result": {}},
        now=now,
    )
    assert updates == {"status": "failed", "updated_at": now}


def test_completed_export_is_never_downgraded_by_failed_job():
    updates = export_updates_from_job(
        _export(status="completed"),
        {"status": "failed", "result": {}},
    )
    assert updates == {}


def test_requeued_job_moves_rendering_export_back_to_queued():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    updates = export_updates_from_job(
        _export(),
        {"status": "queued", "updated_at": now, "result": {}},
        now=now,
    )
    assert updates == {"status": "queued", "updated_at": now}
