"""Stub S3 service for Phase 2.1.

Mimics the AWS S3 presign + download flow but persists to local disk.
- presign_upload() returns a backend-relative URL that accepts PUT
- complete_upload() verifies the file exists on disk
- presign_download() returns a backend-relative URL that streams the file
- delete_object() removes the file

In Phase 2.x we'll swap this for boto3 by changing settings.S3_BACKEND.
"""
from __future__ import annotations

import os
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Tuple

from core.config import settings
from core.security import iso_now, utc_now

BUCKET = "shortcut-stub-bucket"
STORAGE_DIR = Path(settings.STUB_STORAGE_DIR)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _local_path(s3_key: str) -> Path:
    safe = s3_key.replace("..", "_")
    return STORAGE_DIR / safe


def build_key(user_id: str, kind: str, asset_id: str, ext: str) -> str:
    safe_ext = ext.lstrip(".").lower() or "bin"
    return f"users/{user_id}/uploads/{kind}/{asset_id}.{safe_ext}"


def presign_upload(s3_key: str, ttl_seconds: int = 3600) -> Tuple[str, dict, str]:
    """Returns (upload_url, headers, expires_at_iso)."""
    upload_url = f"{settings.APP_PUBLIC_URL}/api/v1/_stub-storage/{s3_key}"
    headers = {"Content-Type": "application/octet-stream"}
    expires_at = (utc_now() + timedelta(seconds=ttl_seconds)).isoformat()
    # Ensure parent dir exists so PUT later can write.
    _local_path(s3_key).parent.mkdir(parents=True, exist_ok=True)
    return upload_url, headers, expires_at


def presign_download(s3_key: str, ttl_seconds: int = 3600) -> str:
    return f"{settings.APP_PUBLIC_URL}/api/v1/_stub-storage/{s3_key}"


def object_exists(s3_key: str) -> bool:
    return _local_path(s3_key).is_file()


def object_size(s3_key: str) -> int:
    p = _local_path(s3_key)
    return p.stat().st_size if p.is_file() else 0


def write_object(s3_key: str, data: bytes) -> int:
    p = _local_path(s3_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        f.write(data)
    return p.stat().st_size


def read_object(s3_key: str) -> bytes:
    p = _local_path(s3_key)
    if not p.is_file():
        raise FileNotFoundError(s3_key)
    return p.read_bytes()


def stream_path(s3_key: str) -> Path:
    return _local_path(s3_key)


def delete_object(s3_key: str) -> bool:
    p = _local_path(s3_key)
    if p.is_file():
        p.unlink(missing_ok=True)
        return True
    return False


__all__ = [
    "BUCKET",
    "build_key",
    "presign_upload",
    "presign_download",
    "object_exists",
    "object_size",
    "write_object",
    "read_object",
    "stream_path",
    "delete_object",
]
