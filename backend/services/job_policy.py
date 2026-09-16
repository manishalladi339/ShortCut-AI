"""Pure job retry/recovery policy helpers."""
from __future__ import annotations


def recovery_status(job: dict) -> str:
    """Return queued while attempts remain, otherwise failed."""
    return (
        "queued"
        if int(job.get("attempt") or 0) < int(job.get("max_attempts") or 1)
        else "failed"
    )
