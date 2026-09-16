"""Schemas for learned creator editing preferences."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PreferenceEvidence(BaseModel):
    total: int = Field(default=0, ge=0)
    kept: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    keep_ratio: float | None = Field(default=None, ge=0, le=1)


class CreatorMemoryOut(BaseModel):
    id: str
    user_id: str
    evidence_count: int = Field(default=0, ge=0)
    plan_feedback_count: int = Field(default=0, ge=0)
    constrained_edit_count: int = Field(default=0, ge=0)
    plan_acceptance_rate: float | None = Field(default=None, ge=0, le=1)
    optional_operation_preferences: dict[str, PreferenceEvidence] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    summary: str
    created_at: datetime
    updated_at: datetime
