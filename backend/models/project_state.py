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


class TransitionKind(str, Enum):
    fade = "fade"


class ClipTransition(BaseModel):
    kind: TransitionKind = TransitionKind.fade
    duration: int = Field(gt=0)


class AudioDucking(BaseModel):
    """Deterministic sidechain-compression settings for an audio clip."""

    enabled: bool = True
    threshold: float = Field(default=0.03, ge=0.00097563, le=1.0)
    ratio: float = Field(default=8.0, ge=1.0, le=20.0)
    attack_ms: float = Field(default=20.0, ge=0.01, le=2000.0)
    release_ms: float = Field(default=350.0, ge=0.01, le=9000.0)
    makeup: float = Field(default=1.0, ge=1.0, le=64.0)


class ClipTransform(BaseModel):
    scale: float = Field(default=1.0, gt=0.01, le=10.0)
    position_x: float = 0.0
    position_y: float = 0.0
    rotation_deg: float = Field(default=0.0, ge=-3600.0, le=3600.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class CaptionCue(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    start: int = Field(ge=0)
    duration: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)
    style: dict[str, Any] = Field(default_factory=dict)


class Clip(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    asset_id: str = Field(min_length=1, max_length=120)
    timeline_start: int = Field(ge=0)
    duration: int = Field(gt=0)
    source_start: int = Field(default=0, ge=0)
    source_duration: int = Field(gt=0)
    loop_source: bool = False
    enabled: bool = True
    volume: float = Field(default=1.0, ge=0.0, le=4.0)
    playback_rate: float = Field(default=1.0, gt=0.05, le=8.0)
    transform: ClipTransform = Field(default_factory=ClipTransform)
    transition_in: ClipTransition | None = None
    transition_out: ClipTransition | None = None
    ducking: AudioDucking | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def transitions_fit_clip(self) -> "Clip":
        for transition in (self.transition_in, self.transition_out):
            if transition and transition.duration > self.duration:
                raise ValueError("transition duration cannot exceed clip duration")
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
    captions: list[CaptionCue] = Field(default_factory=list)

    @model_validator(mode="after")
    def ids_unique(self) -> "Sequence":
        track_ids = [track.id for track in self.tracks]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("track ids must be unique within a sequence")
        clip_ids = [clip.id for track in self.tracks for clip in track.clips]
        if len(clip_ids) != len(set(clip_ids)):
            raise ValueError("clip ids must be unique within a sequence")
        caption_ids = [cue.id for cue in self.captions]
        if len(caption_ids) != len(set(caption_ids)):
            raise ValueError("caption ids must be unique within a sequence")
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
        "remove_track",
        "add_clip",
        "remove_clip",
        "ripple_delete",
        "duplicate_clip",
        "split_clip",
        "move_clip",
        "trim_clip",
        "set_clip_properties",
        "set_track_properties",
        "add_caption",
        "update_caption",
        "remove_caption",
    ]
    payload: dict[str, Any]


class RestoreVersionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class ProjectVersionSummary(BaseModel):
    version: int = Field(ge=1)
    created_at: Any
    operation: str | None = None


class ProjectStateOut(ProjectStateDocument):
    pass
