"""Asset upload, processing and library routes."""
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response

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
        doc = {**doc, "download_url": get_storage().presign_download(doc["storage_key"])}
    return AssetOut(**{k: v for k, v in doc.items() if k != "_id"})


@router.post("/presign-upload", response_model=PresignUploadOut, status_code=status.HTTP_201_CREATED)
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
                detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
            )

    storage = get_storage()
    asset_id = str(uuid.uuid4())
    ext = os.path.splitext(body.filename)[1] or ""
    storage_key = storage.build_key(user["id"], body.kind.value, asset_id, ext)
    upload_url, headers, expires_at = storage.presign_upload(storage_key, ttl_seconds=3600)

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
            detail={"error": {"code": "resource.not_found", "message": "Asset not found"}},
        )

    storage = get_storage()
    if not storage.exists(doc["storage_key"]):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "asset.binary_missing", "message": "Upload not received yet"}},
        )

    actual_size = storage.size(doc["storage_key"])
    if actual_size <= 0:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "asset.empty", "message": "Uploaded file is empty"}},
        )

    # Confirmation is idempotent: do not enqueue duplicate processing jobs.
    if doc.get("upload_status") == UploadStatus.uploaded.value and doc.get("processing_job_id"):
        fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0})
        return _to_out(fresh)

    job = await job_service.enqueue(
        user_id=user["id"],
        project_id=doc.get("project_id"),
        asset_id=asset_id,
        job_type=JobType.media_probe,
    )
    await db.assets.update_one(
        {"id": asset_id, "user_id": user["id"]},
        {
            "$set": {
                "upload_status": UploadStatus.uploaded.value,
                "processing_status": "queued",
                "processing_job_id": job["id"],
                "size_bytes": actual_size,
                "updated_at": utc_now(),
            }
        },
    )
    fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0})
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
        query["filename"] = {"$regex": q, "$options": "i"}

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
            detail={"error": {"code": "resource.not_found", "message": "Asset not found"}},
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
            detail={"error": {"code": "resource.not_found", "message": "Asset not found"}},
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
            detail={"error": {"code": "resource.not_found", "message": "Asset not found"}},
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


@local_storage_router.put("/{storage_key:path}")
async def local_put(storage_key: str, request: Request) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "upload.empty", "message": "Empty body"}},
        )
    written = _local_storage().write_local(storage_key, body)
    return {"ok": True, "bytes": written}


@local_storage_router.get("/{storage_key:path}")
async def local_get(storage_key: str) -> Response:
    path: Path = _local_storage().local_path(storage_key)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "asset.not_found", "message": "Object not found"}},
        )
    return FileResponse(path)
