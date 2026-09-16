"""Asset upload, processing and library routes."""

import os
import re
import mimetypes
from tempfile import NamedTemporaryFile
from core.config import settings
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.asset import (
    AssetListOut,
    AssetOut,
    AssetUpdate,
    ConfirmUploadBody,
    PresignUploadBody,
    PresignUploadOut,
)
from models.common import AssetKind, UploadStatus
from models.job import JobType
from services import job_service
from services.storage import LocalStorage, get_storage

router = APIRouter(prefix="/assets", tags=["assets"])


def _to_out(doc: dict, refresh_download_url: bool = True) -> AssetOut:
    if refresh_download_url and doc.get("upload_status") == UploadStatus.uploaded.value:
        doc = {
            **doc,
            "download_url": get_storage().presign_download(doc["storage_key"]),
        }
    return AssetOut(**{k: v for k, v in doc.items() if k != "_id"})


@router.post(
    "/presign-upload",
    response_model=PresignUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def presign_upload(
    body: PresignUploadBody, user: dict = Depends(get_current_user)
) -> PresignUploadOut:
    db = get_db()
    if body.project_id:
        project = await db.projects.find_one(
            {"id": body.project_id, "user_id": user["id"]}, {"_id": 0, "id": 1}
        )
        if not project:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "resource.not_found",
                        "message": "Project not found",
                    }
                },
            )

    if body.size_bytes > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="File exceeds the configured upload limit"
        )
    storage = get_storage()
    asset_id = str(uuid.uuid4())
    ext = os.path.splitext(body.filename)[1] or ""
    storage_key = storage.build_key(user["id"], body.kind.value, asset_id, ext)
    upload_url, headers, expires_at = storage.presign_upload(
        storage_key, ttl_seconds=3600
    )

    now = utc_now()
    doc = {
        "id": asset_id,
        "user_id": user["id"],
        "project_id": body.project_id,
        "filename": body.filename,
        "mime_type": body.mime_type,
        "kind": body.kind.value,
        "size_bytes": body.size_bytes,
        "duration_sec": None,
        "width": None,
        "height": None,
        "media_metadata": {},
        "storage_type": "s3" if storage.__class__.__name__ == "S3Storage" else "local",
        "storage_bucket": storage.bucket,
        "storage_key": storage_key,
        "download_url": None,
        "upload_status": UploadStatus.pending.value,
        "processing_status": "pending",
        "processing_job_id": None,
        "is_watermarked": False,
        "language": None,
        "tags": body.tags,
        "created_at": now,
        "updated_at": now,
    }
    await db.assets.insert_one(doc)
    return PresignUploadOut(
        asset_id=asset_id,
        upload_url=upload_url,
        upload_headers=headers,
        storage_key=storage_key,
        expires_at=datetime.fromisoformat(expires_at),
    )


@router.post("/{asset_id}/confirm", response_model=AssetOut)
async def confirm_upload(
    asset_id: str,
    _body: ConfirmUploadBody,
    user: dict = Depends(get_current_user),
) -> AssetOut:
    db = get_db()
    doc = await db.assets.find_one({"id": asset_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "resource.not_found", "message": "Asset not found"}
            },
        )

    storage = get_storage()
    if not storage.exists(doc["storage_key"]):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "asset.binary_missing",
                    "message": "Upload not received yet",
                }
            },
        )

    actual_size = storage.size(doc["storage_key"])
    if actual_size > settings.MAX_UPLOAD_BYTES or actual_size != doc["size_bytes"]:
        raise HTTPException(
            status_code=400,
            detail="Uploaded size does not match the declared file size",
        )
    if actual_size <= 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "asset.empty", "message": "Uploaded file is empty"}
            },
        )

    job_id = doc.get("processing_job_id") or str(uuid.uuid4())
    # Atomically reserve a single job ID before queueing it. Reconfirmation repairs
    # a process interruption between the database update and enqueue.
    await db.assets.update_one(
        {"id": asset_id, "user_id": user["id"], "processing_job_id": None},
        {
            "$set": {
                "upload_status": "uploaded",
                "processing_status": "queued",
                "processing_job_id": job_id,
                "updated_at": utc_now(),
            }
        },
    )
    fresh = await db.assets.find_one(
        {"id": asset_id, "user_id": user["id"]}, {"_id": 0}
    )
    await job_service.enqueue(
        user_id=user["id"],
        project_id=doc.get("project_id"),
        asset_id=asset_id,
        job_type=JobType.media_probe,
        job_id=fresh["processing_job_id"],
    )
    return _to_out(fresh)


@router.get("", response_model=AssetListOut)
async def list_assets(
    kind: AssetKind | None = None,
    project_id: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> AssetListOut:
    db = get_db()
    query: dict = {"user_id": user["id"]}
    if kind:
        query["kind"] = kind.value
    if project_id:
        query["project_id"] = project_id
    if tag:
        query["tags"] = tag
    if q:
        query["filename"] = {"$regex": re.escape(q[:255]), "$options": "i"}

    cursor = db.assets.find(query, {"_id": 0}).sort("created_at", -1).limit(limit + 1)
    docs = await cursor.to_list(limit + 1)
    has_more = len(docs) > limit
    docs = docs[:limit]
    return AssetListOut(items=[_to_out(doc) for doc in docs], has_more=has_more)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: str, user: dict = Depends(get_current_user)) -> AssetOut:
    doc = await get_db().assets.find_one(
        {"id": asset_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "resource.not_found", "message": "Asset not found"}
            },
        )
    return _to_out(doc)


@router.patch("/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: str, body: AssetUpdate, user: dict = Depends(get_current_user)
) -> AssetOut:
    db = get_db()
    update: dict = {"updated_at": utc_now()}
    if body.filename is not None:
        update["filename"] = body.filename
    if body.tags is not None:
        update["tags"] = body.tags

    result = await db.assets.update_one(
        {"id": asset_id, "user_id": user["id"]}, {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "resource.not_found", "message": "Asset not found"}
            },
        )
    fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    return _to_out(fresh)


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    doc = await db.assets.find_one({"id": asset_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "resource.not_found", "message": "Asset not found"}
            },
        )

    get_storage().delete(doc["storage_key"])
    await db.jobs.delete_many({"asset_id": asset_id, "user_id": user["id"]})
    await db.assets.delete_one({"id": asset_id, "user_id": user["id"]})
    return {"ok": True}


local_storage_router = APIRouter(prefix="/_local-storage", tags=["local-storage"])


def _local_storage() -> LocalStorage:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Local storage endpoint disabled")
    return storage


def _verify_local(
    storage_key: str, method: str, expires: int, signature: str
) -> LocalStorage:
    storage = _local_storage()
    if not storage.verify_signature(storage_key, method, expires, signature):
        raise HTTPException(status_code=403, detail="Invalid or expired file link")
    try:
        storage.local_path(storage_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid object key")
    return storage


@local_storage_router.put("/{storage_key:path}")
async def local_put(
    storage_key: str, request: Request, expires: int = 0, signature: str = ""
) -> dict:
    storage = _verify_local(storage_key, "PUT", expires, signature)
    asset = await get_db().assets.find_one(
        {"storage_key": storage_key, "upload_status": "pending"}
    )
    if not asset:
        raise HTTPException(status_code=409, detail="Upload is no longer pending")
    path = storage.local_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > min(settings.MAX_UPLOAD_BYTES, asset["size_bytes"]):
                    raise HTTPException(
                        status_code=413, detail="Upload exceeds declared size"
                    )
                stream.write(chunk)
        if size != asset["size_bytes"]:
            raise HTTPException(status_code=400, detail="Incomplete upload")
        # Link is atomic and never overwrites an already uploaded binary.
        try:
            os.link(temp_path, path)
        except FileExistsError:
            raise HTTPException(
                status_code=409,
                detail="File already uploaded; confirm it or create a new upload",
            )
        return {"ok": True, "bytes": size}
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


@local_storage_router.get("/{storage_key:path}")
async def local_get(
    storage_key: str, request: Request, expires: int = 0, signature: str = ""
) -> Response:
    storage = _verify_local(storage_key, "GET", expires, signature)
    path = storage.local_path(storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Object not found")
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
        "Accept-Ranges": "bytes",
    }
    size = path.stat().st_size
    requested = request.headers.get("range")
    if not requested:
        return FileResponse(path, headers=headers)
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
    if not match or not any(match.groups()):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    start_text, end_text = match.groups()
    start = int(start_text) if start_text else max(0, size - int(end_text))
    end = min(size - 1, int(end_text)) if start_text and end_text else size - 1
    if start >= size or end < start:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    def chunks():
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers.update(
        {
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1),
        }
    )
    return StreamingResponse(
        chunks(),
        status_code=206,
        headers=headers,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    )
