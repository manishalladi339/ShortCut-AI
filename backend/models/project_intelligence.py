"""Schemas for whole-project intelligence synthesized from analyzed media."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectEvidence(BaseModel):
    asset_id: str
    intelligence_id: str
    unit_index: int = Field(ge=0)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    speakers: list[str] = Field(default_factory=list)
    relevance_to_topic: float = Field(ge=-1, le=1)


class ProjectTopic(BaseModel):
    id: str
    label: str
    unit_count: int = Field(ge=1)
    asset_ids: list[str] = Field(default_factory=list)
    member_keys: list[str] = Field(default_factory=list)
    evidence: list[ProjectEvidence] = Field(default_factory=list)


class SpeakerPresence(BaseModel):
    asset_id: str
    speaker: str
    unit_count: int = Field(ge=1)
    spoken_duration_sec: float = Field(ge=0)


class VisualLibrarySummary(BaseModel):
    observation_count: int = Field(ge=0)
    observations_with_people: int = Field(ge=0)
    observations_with_text: int = Field(ge=0)
    common_objects: list[dict[str, Any]] = Field(default_factory=list)
    shot_types: list[dict[str, Any]] = Field(default_factory=list)


class ProjectIntelligenceOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    status: str = "completed"
    asset_count: int = Field(ge=0)
    semantic_unit_count: int = Field(ge=0)
    visual_observation_count: int = Field(ge=0)
    source_intelligence_ids: list[str] = Field(default_factory=list)
    asset_summaries: list[dict[str, Any]] = Field(default_factory=list)
    speaker_presences: list[SpeakerPresence] = Field(default_factory=list)
    topic_clusters: list[ProjectTopic] = Field(default_factory=list)
    visual_library: VisualLibrarySummary
    summary: str
    created_at: datetime
    updated_at: datetime
