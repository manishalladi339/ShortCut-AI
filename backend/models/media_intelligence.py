"""Schemas for time-aligned multimodal media intelligence."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TranscriptWord(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(min_length=1)
    speaker: str | None = None


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(min_length=1)
    speaker: str | None = None


class SceneBoundary(BaseModel):
    start: float = Field(ge=0)
    end: float | None = Field(default=None, ge=0)
    score: float | None = None


class SilenceInterval(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(ge=0)


class RhythmEvent(BaseModel):
    time: float = Field(ge=0)
    strength: float = Field(ge=0, le=1)
    energy: float = Field(ge=0)
    energy_ratio: float = Field(ge=0)


class VisualObservation(BaseModel):
    index: int = Field(ge=0)
    time: float = Field(ge=0)
    description: str = ""
    shot_type: str = "unknown"
    people_count: int = Field(default=0, ge=0)
    visible_objects: list[str] = Field(default_factory=list)
    text_on_screen: str | None = None
    editing_notes: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class MediaIntelligenceOut(BaseModel):
    id: str
    asset_id: str
    user_id: str
    project_id: str | None = None
    status: str
    language: str | None = None
    transcript_text: str = ""
    words: list[TranscriptWord] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    diarized: bool = False
    scenes: list[SceneBoundary] = Field(default_factory=list)
    silences: list[SilenceInterval] = Field(default_factory=list)
    rhythm_events: list[RhythmEvent] = Field(default_factory=list)
    visual_observations: list[VisualObservation] = Field(default_factory=list)
    semantic_units: list[dict[str, Any]] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime


class AnalyzeAssetOut(BaseModel):
    job_id: str
    intelligence_id: str
    status: str
