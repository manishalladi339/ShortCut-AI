"""Schemas for localized, reviewable Create-With-Me edit proposals."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CreateConstrainedEditRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=1200)
    scope_start_sec: float | None = Field(default=None, ge=0, le=7200)
    scope_end_sec: float | None = Field(default=None, gt=0, le=7200)

    @model_validator(mode="after")
    def scope_is_ordered(self) -> "CreateConstrainedEditRequest":
        if (
            self.scope_start_sec is not None
            and self.scope_end_sec is not None
            and self.scope_end_sec <= self.scope_start_sec
        ):
            raise ValueError("scope_end_sec must be greater than scope_start_sec")
        return self


class ConstrainedEditOperation(BaseModel):
    id: str
    operation: Literal[
        "remove_clip",
        "set_clip_properties",
        "update_caption",
        "remove_caption",
        "remove_speaker_ripple",
    ]
    component: Literal["story", "broll", "music", "captions"]
    payload: dict[str, Any]
    reason: str


class ConstrainedEditProposalOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    project_state_version: int = Field(ge=1)
    status: Literal["proposed", "applied", "rejected"]
    instruction: str
    interpreted_intents: list[str] = Field(default_factory=list)
    scope_start_sec: float = Field(ge=0)
    scope_end_sec: float = Field(gt=0)
    preserve_rules: list[str] = Field(default_factory=list)
    summary: str
    operations: list[ConstrainedEditOperation] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    applied_project_state_version: int | None = None
    applied_operation_ids: list[str] = Field(default_factory=list)
    skipped_operation_ids: list[str] = Field(default_factory=list)


class ApplyConstrainedEditRequest(BaseModel):
    expected_version: int = Field(ge=1)
    operation_ids: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
