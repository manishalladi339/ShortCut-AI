"""Schemas for auditable AI edit-plan proposals."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
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
    narrative_role: str | None = None
    speakers: list[str] = Field(default_factory=list)
    primary_speaker: str | None = None
    source_segments: list[dict[str, float]] = Field(default_factory=list)
    dead_air_removed_sec: float = Field(default=0.0, ge=0.0)
    planned_duration_sec: float | None = Field(default=None, ge=0.0)
    visual_context: dict[str, Any] | None = None


class BrollRecommendation(BaseModel):
    for_asset_id: str
    for_unit_index: int = Field(ge=0)
    timeline_start: int = Field(ge=0)
    duration: int = Field(gt=0)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    rhythm_event: dict[str, Any] | None = None


class ProposedEditOperation(BaseModel):
    id: str | None = None
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
    broll_recommendations: list[BrollRecommendation] = Field(default_factory=list)
    audience_profile: dict[str, Any] = Field(default_factory=dict)
    narrative_summary: str = ""
    caption_suggestion: str = ""
    cta_suggestion: str = ""
    narrative_provider: str | None = None
    narrative_model: str | None = None
    evaluation: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    applied_project_state_version: int | None = None
    feedback_outcome: str | None = None
    applied_operation_ids: list[str] = Field(default_factory=list)
    skipped_operation_ids: list[str] = Field(default_factory=list)


class ApplyAIEditPlanRequest(BaseModel):
    expected_version: int = Field(ge=1)
    replace_existing_video_clips: bool = False
    operation_ids: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )


class CreateAIEditPlanRequest(BaseModel):
    objective: str | None = Field(default=None, max_length=2000)
    target_audience: str | None = Field(default=None, max_length=500)
    target_duration_sec: float = Field(default=45.0, ge=5.0, le=300.0)
    max_clips: int = Field(default=8, ge=1, le=30)
    min_clip_sec: float = Field(default=2.0, ge=0.5, le=30.0)
    max_clip_sec: float = Field(default=20.0, ge=1.0, le=60.0)
    include_captions: bool = True
    include_speakers: list[str] = Field(default_factory=list, max_length=10)
    exclude_speakers: list[str] = Field(default_factory=list, max_length=10)
    max_same_speaker_run: int = Field(default=2, ge=1, le=5)
    remove_dead_air: bool = True
    dead_air_min_sec: float = Field(default=0.9, ge=0.5, le=5.0)
    rhythm_snap_broll: bool = True
    rhythm_snap_window_sec: float = Field(default=0.35, ge=0.0, le=1.0)
    broll_fade: bool = True
    broll_fade_sec: float = Field(default=0.18, ge=0.05, le=1.0)
    music_asset_id: str | None = Field(default=None, max_length=120)
    music_source_start_sec: float = Field(default=0.0, ge=0.0, le=7200.0)
    music_volume: float = Field(default=0.12, ge=0.0, le=1.0)
    music_fade_sec: float = Field(default=0.75, ge=0.05, le=5.0)
    music_fit_mode: Literal["strict", "loop"] = "strict"
    music_loop_crossfade_sec: float = Field(default=0.25, ge=0.05, le=2.0)
    music_ducking: bool = True
    music_duck_threshold: float = Field(default=0.03, ge=0.00097563, le=1.0)
    music_duck_ratio: float = Field(default=8.0, ge=1.0, le=20.0)
    music_duck_attack_ms: float = Field(default=20.0, ge=0.01, le=2000.0)
    music_duck_release_ms: float = Field(default=350.0, ge=0.01, le=9000.0)
