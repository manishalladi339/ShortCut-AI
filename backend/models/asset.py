"""Asset Pydantic schemas."""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from models.common import AssetKind, UploadStatus


class PresignUploadBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    kind: AssetKind
    size_bytes: int = Field(ge=1, le=5 * 1024 * 1024 * 1024)
    project_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PresignUploadOut(BaseModel):
    asset_id: str
    upload_url: str
    upload_headers: dict
    storage_key: str
    expires_at: datetime


class ConfirmUploadBody(BaseModel):
    """The server probes metadata asynchronously; client values are not trusted."""
    pass


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
    media_metadata: dict[str, Any] = Field(default_factory=dict)

    storage_type: str
    storage_bucket: str
    storage_key: str
    download_url: Optional[str] = None

    upload_status: UploadStatus
    processing_status: str = "pending"
    processing_job_id: Optional[str] = None

    is_watermarked: bool = False
    language: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AssetListOut(BaseModel):
    items: List[AssetOut]
    next_cursor: Optional[str] = None
    has_more: bool = False
