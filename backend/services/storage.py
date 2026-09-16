"""Object-storage abstraction with local and S3 backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import hashlib
import hmac
import time
from urllib.parse import quote
import shutil

import boto3
from botocore.exceptions import ClientError

from core.config import settings
from core.security import utc_now


class StorageBackend(ABC):
    bucket: str

    @abstractmethod
    def build_key(self, user_id: str, kind: str, asset_id: str, ext: str) -> str: ...

    @abstractmethod
    def presign_upload(
        self, key: str, ttl_seconds: int = 3600
    ) -> tuple[str, dict, str]: ...

    @abstractmethod
    def presign_download(self, key: str, ttl_seconds: int = 3600) -> str: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def size(self, key: str) -> int: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def write_local(self, key: str, data: bytes) -> int: ...

    @abstractmethod
    def local_path(self, key: str) -> Path: ...

    @abstractmethod
    def download_to(self, key: str, destination: Path) -> None: ...

    @abstractmethod
    def upload_file(
        self, key: str, source: Path, content_type: str | None = None
    ) -> None: ...

    @staticmethod
    def _build_key(user_id: str, kind: str, asset_id: str, ext: str) -> str:
        safe_ext = ext.lstrip(".").lower() or "bin"
        return f"users/{user_id}/uploads/{kind}/{asset_id}.{safe_ext}"


class LocalStorage(StorageBackend):
    def __init__(self) -> None:
        self.bucket = "shortcut-local"
        self.root = Path(settings.STUB_STORAGE_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def build_key(self, user_id: str, kind: str, asset_id: str, ext: str) -> str:
        return self._build_key(user_id, kind, asset_id, ext)

    def local_path(self, key: str) -> Path:
        candidate_key = Path(key)
        if candidate_key.is_absolute() or ".." in candidate_key.parts:
            raise ValueError("invalid object key")
        candidate = (self.root / candidate_key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("object key escapes storage root")
        return candidate

    def signed_url(self, key: str, method: str, ttl_seconds: int) -> str:
        expires = int(time.time()) + ttl_seconds
        signature = hmac.new(
            settings.JWT_SECRET.encode(),
            f"{method}\n{key}\n{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{settings.APP_PUBLIC_URL.rstrip('/')}/api/v1/_local-storage/{quote(key, safe='/')}?expires={expires}&signature={signature}"

    def verify_signature(
        self, key: str, method: str, expires: int, signature: str
    ) -> bool:
        expected = hmac.new(
            settings.JWT_SECRET.encode(),
            f"{method}\n{key}\n{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return expires >= int(time.time()) and hmac.compare_digest(expected, signature)

    def presign_upload(
        self, key: str, ttl_seconds: int = 3600
    ) -> tuple[str, dict, str]:
        self.local_path(key).parent.mkdir(parents=True, exist_ok=True)
        return (
            self.signed_url(key, "PUT", ttl_seconds),
            {"Content-Type": "application/octet-stream"},
            (utc_now() + timedelta(seconds=ttl_seconds)).isoformat(),
        )

    def presign_download(self, key: str, ttl_seconds: int = 3600) -> str:
        return self.signed_url(key, "GET", ttl_seconds)

    def exists(self, key: str) -> bool:
        return self.local_path(key).is_file()

    def size(self, key: str) -> int:
        path = self.local_path(key)
        return path.stat().st_size if path.is_file() else 0

    def delete(self, key: str) -> bool:
        path = self.local_path(key)
        if path.is_file():
            path.unlink()
            return True
        return False

    def write_local(self, key: str, data: bytes) -> int:
        path = self.local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.stat().st_size

    def download_to(self, key: str, destination: Path) -> None:
        source = self.local_path(key)
        if not source.is_file():
            raise FileNotFoundError(key)
        shutil.copyfile(source, destination)

    def upload_file(
        self, key: str, source: Path, content_type: str | None = None
    ) -> None:
        destination = self.local_path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET
        if not self.bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
        )

    def build_key(self, user_id: str, kind: str, asset_id: str, ext: str) -> str:
        return self._build_key(user_id, kind, asset_id, ext)

    def presign_upload(
        self, key: str, ttl_seconds: int = 3600
    ) -> tuple[str, dict, str]:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "IfNoneMatch": "*"},
            ExpiresIn=ttl_seconds,
        )
        return (
            url,
            {"Content-Type": "application/octet-stream", "If-None-Match": "*"},
            (utc_now() + timedelta(seconds=ttl_seconds)).isoformat(),
        )

    def presign_download(self, key: str, ttl_seconds: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise

    def size(self, key: str) -> int:
        response = self.client.head_object(Bucket=self.bucket, Key=key)
        return int(response["ContentLength"])

    def delete(self, key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True

    def write_local(self, key: str, data: bytes) -> int:
        raise RuntimeError("local PUT endpoint is disabled for S3 storage")

    def local_path(self, key: str) -> Path:
        raise RuntimeError("S3 objects do not have a persistent local path")

    def download_to(self, key: str, destination: Path) -> None:
        self.client.download_file(self.bucket, key, str(destination))

    def upload_file(
        self, key: str, source: Path, content_type: str | None = None
    ) -> None:
        extra = {"ContentType": content_type} if content_type else None
        if extra:
            self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra)
        else:
            self.client.upload_file(str(source), self.bucket, key)


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        backend = settings.STORAGE_BACKEND.lower()
        if backend == "local":
            _storage = LocalStorage()
        elif backend == "s3":
            _storage = S3Storage()
        else:
            raise RuntimeError(
                f"Unsupported STORAGE_BACKEND: {settings.STORAGE_BACKEND}"
            )
    return _storage


@contextmanager
def materialize(key: str, suffix: str = "") -> Iterator[Path]:
    storage = get_storage()
    if isinstance(storage, LocalStorage):
        yield storage.local_path(key)
        return

    with TemporaryDirectory(prefix="shortcut-media-") as temp_dir:
        destination = Path(temp_dir) / f"asset{suffix}"
        storage.download_to(key, destination)
        yield destination
