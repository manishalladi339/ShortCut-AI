"""Structured quality-assurance report for a rendered export."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExportQAIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    category: Literal["timeline", "visual", "audio", "captions"]
    message: str
    start_sec: float | None = Field(default=None, ge=0)
    end_sec: float | None = Field(default=None, ge=0)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_action: str | None = None
    auto_fixable: bool = False


class ExportQACheck(BaseModel):
    id: str
    status: Literal["passed", "warning", "failed"]
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExportQAReport(BaseModel):
    status: Literal["passed", "warnings", "failed"]
    issue_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    issues: list[ExportQAIssue] = Field(default_factory=list)
    checks: list[ExportQACheck] = Field(default_factory=list)
    generated_at: datetime
