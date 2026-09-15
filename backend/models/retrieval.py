"""Semantic and visual retrieval API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=8, ge=1, le=50)
    min_score: float = Field(default=0.15, ge=-1.0, le=1.0)


class SemanticSearchHit(BaseModel):
    score: float
    asset_id: str
    intelligence_id: str
    unit_index: int
    start: float
    end: float
    text: str


class SemanticSearchOut(BaseModel):
    query: str
    model: str
    hits: list[SemanticSearchHit]


class VisualSearchHit(BaseModel):
    relevance_score: float
    asset_id: str
    intelligence_id: str
    observation_index: int
    time: float
    description: str
    shot_type: str = "unknown"
    visible_objects: list[str] = Field(default_factory=list)
    text_on_screen: str | None = None


class VisualSearchOut(BaseModel):
    query: str
    model: str
    hits: list[VisualSearchHit]
