"""Tests for durable export recovery from job state."""
from datetime import datetime, timezone

from services.export_recovery import export_updates_from_job


NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


def test_succeeded_job_repairs_incomplete_export():
    doc = {
        "id": "export-1",
        "status": "rendering",
        "active": True,
    }
    job = {
        "status": "succeeded",
        "finished_at": NOW,
        "result": {
            "export_id": "export-1",
            "storage_key": "exports/export-1.mp4",
            "duration_sec": 42.5,
            "render_metadata": {"width": 1080, "height": 1920},
            "qa_status": "warnings",
            "qa_report": {"status": "warnings", "issue_count": 1},
        },
    }

    updates = export_updates_from_job(doc, job, fallback_now=NOW)
    assert updates["status"] == "completed"
    assert updates["active"] is False
    assert updates["storage_key"] == "exports/export-1.mp4"
    assert updates["duration_sec"] == 42.5
    assert updates["qa_status"] == "warnings"


def test_failed_job_marks_noncompleted_export_terminal():
    updates = export_updates_from_job(
        {"id": "export-1", "status": "rendering", "active": True},
        {"status": "failed", "finished_at": NOW, "result": {}},
        fallback_now=NOW,
    )
    assert updates == {
        "status": "failed",
        "active": False,
        "updated_at": NOW,
    }


def test_requeued_job_moves_rendering_export_back_to_queue():
    updates = export_updates_from_job(
        {"id": "export-1", "status": "rendering", "active": True},
        {"status": "queued", "updated_at": NOW, "result": {}},
        fallback_now=NOW,
    )
    assert updates == {
        "status": "queued",
        "active": True,
        "updated_at": NOW,
    }


def test_wrong_succeeded_job_cannot_complete_another_export():
    updates = export_updates_from_job(
        {"id": "export-1", "status": "rendering", "active": True},
        {
            "status": "succeeded",
            "result": {
                "export_id": "export-2",
                "storage_key": "exports/export-2.mp4",
            },
        },
        fallback_now=NOW,
    )
    assert updates == {}


def test_completed_export_is_not_downgraded_by_failed_job():
    updates = export_updates_from_job(
        {"id": "export-1", "status": "completed", "active": False},
        {"status": "failed", "finished_at": NOW, "result": {}},
        fallback_now=NOW,
    )
    assert updates == {}
