"""Deterministic render-plan schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RenderCaption(BaseModel):
    id: str
    start: int = Field(ge=0)
    duration: int = Field(gt=0)
    text: str
    style: dict[str, Any] = Field(default_factory=dict)


class RenderTransition(BaseModel):
    kind: str
    duration: int = Field(gt=0)


class RenderClip(BaseModel):
    clip_id: str
    track_id: str
    track_kind: str
    track_index: int = Field(ge=0)
    asset_id: str
    source_storage_key: str
    timeline_start: int = Field(ge=0)
    duration: int = Field(gt=0)
    source_start: int = Field(ge=0)
    source_duration: int = Field(gt=0)
    playback_rate: float = Field(gt=0)
    volume: float = Field(ge=0)
    transition_in: RenderTransition | None = None
    transition_out: RenderTransition | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderPlan(BaseModel):
    project_id: str
    project_state_version: int = Field(ge=1)
    sequence_id: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    timebase_numerator: int = Field(gt=0)
    timebase_denominator: int = Field(gt=0)
    duration_ticks: int = Field(ge=0)
    clips: list[RenderClip] = Field(default_factory=list)
    captions: list[RenderCaption] = Field(default_factory=list)
