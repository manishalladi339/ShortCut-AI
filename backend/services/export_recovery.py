"""Pure export/job reconciliation policy."""
from __future__ import annotations


def export_updates_from_job(doc: dict, job: dict, *, fallback_now) -> dict:
    """Return export fields implied by a durable job state."""
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
                "updated_at": (
                    job.get("finished_at")
                    or job.get("updated_at")
                    or fallback_now
                ),
            }

    if job.get("status") == "failed" and doc.get("status") != "completed":
        return {
            "status": "failed",
            "active": False,
            "updated_at": (
                job.get("finished_at")
                or job.get("updated_at")
                or fallback_now
            ),
        }

    if job.get("status") == "queued" and doc.get("status") == "rendering":
        return {
            "status": "queued",
            "active": True,
            "updated_at": job.get("updated_at") or fallback_now,
        }

    return {}
