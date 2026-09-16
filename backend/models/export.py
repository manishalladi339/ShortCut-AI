"""Export request and artifact schemas."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from models.export_qa import ExportQAReport


class ExportRequest(BaseModel):
    sequence_id: str | None = None
    preset: str = Field(default="vertical_1080p", pattern="^(vertical_1080p|source)$")


class ExportOut(BaseModel):
    id: str
    user_id: str
    project_id: str
    sequence_id: str
    project_state_version: int
    status: str
    preset: str
    job_id: str
    storage_key: str | None = None
    download_url: str | None = None
    duration_sec: float | None = None
    render_metadata: dict = Field(default_factory=dict)
    qa_status: str | None = None
    qa_report: ExportQAReport | None = None
    created_at: datetime
    updated_at: datetime
