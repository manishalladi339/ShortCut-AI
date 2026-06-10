"""Asset Pydantic schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models.common import AssetKind, UploadStatus


class PresignUploadBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    kind: AssetKind
    size_bytes: int = Field(ge=1, le=1024 * 1024 * 1024)  # 1 byte – 1 GB
    project_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PresignUploadOut(BaseModel):
    asset_id: str
    upload_url: str
    upload_headers: dict
    s3_key: str
    expires_at: datetime


class ConfirmUploadBody(BaseModel):
    duration_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


class AssetUpdate(BaseModel):
    filename: Optional[str] = Field(default=None, min_length=1, max_length=255)
    tags: Optional[List[str]] = None


class AssetOut(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    filename: str
    mime_type: str
    kind: AssetKind
    size_bytes: int
    duration_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    storage_type: str = "s3"
    s3_bucket: str
    s3_key: str
    s3_url: Optional[str] = None  # signed GET URL, ephemeral
    upload_status: UploadStatus
    is_watermarked: bool = False
    language: Optional[str] = "en"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AssetListOut(BaseModel):
    items: List[AssetOut]
    next_cursor: Optional[str] = None
    has_more: bool = False
