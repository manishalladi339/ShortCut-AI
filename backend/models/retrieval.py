"""Semantic retrieval API schemas."""
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
