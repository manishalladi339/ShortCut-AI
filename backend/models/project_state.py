"""Canonical non-destructive editing state for ShortCut AI."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TrackKind(str, Enum):
    video = "video"
    audio = "audio"
    caption = "caption"
    overlay = "overlay"


class Timebase(BaseModel):
    """Ticks per second = numerator / denominator."""

    numerator: int = Field(default=1000, gt=0)
    denominator: int = Field(default=1, gt=0)


class Clip(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    asset_id: str = Field(min_length=1, max_length=120)
    timeline_start: int = Field(ge=0)
    duration: int = Field(gt=0)
    source_start: int = Field(default=0, ge=0)
    source_duration: int = Field(gt=0)
    enabled: bool = True
    volume: float = Field(default=1.0, ge=0.0, le=4.0)
    playback_rate: float = Field(default=1.0, gt=0.05, le=8.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def source_range_is_valid(self) -> "Clip":
        if self.source_duration <= 0:
            raise ValueError("source_duration must be positive")
        return self


class Track(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    kind: TrackKind
    name: str = Field(min_length=1, max_length=120)
    locked: bool = False
    muted: bool = False
    clips: list[Clip] = Field(default_factory=list)

    @model_validator(mode="after")
    def clip_ids_unique(self) -> "Track":
        ids = [clip.id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("clip ids must be unique within a track")
        return self


class Sequence(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    width: int = Field(default=1080, gt=0, le=8192)
    height: int = Field(default=1920, gt=0, le=8192)
    timebase: Timebase = Field(default_factory=Timebase)
    tracks: list[Track] = Field(default_factory=list)

    @model_validator(mode="after")
    def track_ids_unique(self) -> "Sequence":
        ids = [track.id for track in self.tracks]
        if len(ids) != len(set(ids)):
            raise ValueError("track ids must be unique within a sequence")
        clip_ids = [clip.id for track in self.tracks for clip in track.clips]
        if len(clip_ids) != len(set(clip_ids)):
            raise ValueError("clip ids must be unique within a sequence")
        return self


class ProjectStateDocument(BaseModel):
    project_id: str
    user_id: str
    version: int = Field(default=1, ge=1)
    active_sequence_id: str
    sequences: list[Sequence]
    created_at: Any
    updated_at: Any

    @model_validator(mode="after")
    def active_sequence_exists(self) -> "ProjectStateDocument":
        ids = [sequence.id for sequence in self.sequences]
        if len(ids) != len(set(ids)):
            raise ValueError("sequence ids must be unique")
        if self.active_sequence_id not in ids:
            raise ValueError("active_sequence_id must reference an existing sequence")
        return self


class ProjectStateReplace(BaseModel):
    expected_version: int = Field(ge=1)
    active_sequence_id: str
    sequences: list[Sequence]


class EditOperation(BaseModel):
    """A deterministic mutation that can be proposed by humans or AI."""

    expected_version: int = Field(ge=1)
    operation: Literal[
        "set_active_sequence",
        "rename_sequence",
        "add_track",
        "remove_clip",
        "move_clip",
        "trim_clip",
    ]
    payload: dict[str, Any]


class ProjectStateOut(ProjectStateDocument):
    pass
