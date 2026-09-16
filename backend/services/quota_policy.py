"""Dependency-light project quota policy helpers."""
from __future__ import annotations

from datetime import datetime, timezone


def quota_period(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m")
