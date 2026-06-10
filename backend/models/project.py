"""Project Pydantic schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models.common import ContentType, CreationMode, Platform, ProjectStatus, Style


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    content_type: ContentType
    creation_mode: CreationMode
    desired_style: Optional[Style] = None
    target_platforms: List[Platform] = Field(default_factory=list)
    prompt: Optional[str] = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    desired_style: Optional[Style] = None
    target_platforms: Optional[List[Platform]] = None
    prompt: Optional[str] = Field(default=None, max_length=4000)


class ProjectOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    content_type: ContentType
    creation_mode: CreationMode
    status: ProjectStatus
    desired_style: Optional[Style] = None
    target_platforms: List[Platform] = Field(default_factory=list)
    prompt: Optional[str] = None
    primary_asset_id: Optional[str] = None
    output_clip_ids: List[str] = Field(default_factory=list)
    output_thumbnail_ids: List[str] = Field(default_factory=list)
    current_ai_job_id: Optional[str] = None
    archived: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectListOut(BaseModel):
    items: List[ProjectOut]
    next_cursor: Optional[str] = None
    has_more: bool = False
