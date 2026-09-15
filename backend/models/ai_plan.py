"""Schemas for auditable AI edit-plan proposals."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HighlightCandidate(BaseModel):
    asset_id: str
    intelligence_id: str
    unit_index: int = Field(ge=0)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str
    heuristic_score: float = Field(ge=0, le=1)
    relevance_score: float = Field(ge=-1, le=1)
    final_score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class ProposedEditOperation(BaseModel):
    operation: str
    payload: dict[str, Any]
    reason: str


class AIEditPlanOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    project_state_version: int = Field(ge=1)
    status: str
    objective: str
    target_duration_sec: float = Field(gt=0)
    candidates: list[HighlightCandidate] = Field(default_factory=list)
    operations: list[ProposedEditOperation] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateAIEditPlanRequest(BaseModel):
    objective: str | None = Field(default=None, max_length=2000)
    target_duration_sec: float = Field(default=45.0, ge=5.0, le=300.0)
    max_clips: int = Field(default=8, ge=1, le=30)
    min_clip_sec: float = Field(default=2.0, ge=0.5, le=30.0)
    max_clip_sec: float = Field(default=20.0, ge=1.0, le=60.0)
