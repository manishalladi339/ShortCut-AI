"""Background processing job schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobType(str, Enum):
    create_for_me = "create_for_me"
    media_probe = "media_probe"
    render_export = "render_export"
    media_intelligence = "media_intelligence"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobOut(BaseModel):
    id: str
    user_id: str
    project_id: str | None = None
    asset_id: str | None = None
    type: JobType
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    error_code: str | None = None
    error_message: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
