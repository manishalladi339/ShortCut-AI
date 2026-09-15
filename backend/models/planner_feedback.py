"""Planner feedback and aggregate evaluation schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PlannerFeedbackRequest(BaseModel):
    outcome: Literal["accepted", "rejected", "modified"]
    notes: str | None = Field(default=None, max_length=2000)


class PlannerFeedbackOut(BaseModel):
    plan_id: str
    project_id: str
    user_id: str
    outcome: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PlannerMetricsOut(BaseModel):
    total_feedback: int
    accepted: int
    rejected: int
    modified: int
    acceptance_rate: float
