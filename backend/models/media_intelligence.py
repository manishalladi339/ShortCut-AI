"""Schemas for time-aligned media intelligence."""
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
    scenes: list[SceneBoundary] = Field(default_factory=list)
    semantic_units: list[dict[str, Any]] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime


class AnalyzeAssetOut(BaseModel):
    job_id: str
    intelligence_id: str
    status: str
