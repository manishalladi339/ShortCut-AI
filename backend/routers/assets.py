"""Asset router — presigned upload + confirm + list + get + delete.

Uses stub S3 (local disk) backend; will swap to AWS S3 (boto3) without
changing the route contract.
"""
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request, status
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
from services import s3_service

router = APIRouter(prefix="/assets", tags=["assets"])


def _to_out(doc: dict, refresh_signed_url: bool = True) -> AssetOut:
    if refresh_signed_url and doc.get("upload_status") == UploadStatus.uploaded.value:
        doc = {**doc, "s3_url": s3_service.presign_download(doc["s3_key"])}
    return AssetOut(**{k: v for k, v in doc.items() if k != "_id"})


@router.post("/presign-upload", response_model=PresignUploadOut, status_code=status.HTTP_201_CREATED)
async def presign_upload(body: PresignUploadBody, user: dict = Depends(get_current_user)) -> PresignUploadOut:
    db = get_db()
    if body.project_id:
        proj = await db.projects.find_one(
            {"id": body.project_id, "user_id": user["id"]}, {"_id": 0, "id": 1}
        )
        if not proj:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
            )
    asset_id = str(uuid.uuid4())
    ext = os.path.splitext(body.filename)[1] or ""
    s3_key = s3_service.build_key(user["id"], body.kind.value, asset_id, ext)
    upload_url, headers, expires_at = s3_service.presign_upload(s3_key, ttl_seconds=3600)

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
        "storage_type": "s3",
        "s3_bucket": s3_service.BUCKET,
        "s3_key": s3_key,
        "s3_url": None,
        "upload_status": UploadStatus.pending.value,
        "is_watermarked": False,
        "language": "en",
        "tags": body.tags,
        "created_at": now,
        "updated_at": now,
    }
    await db.assets.insert_one(doc)
    return PresignUploadOut(
        asset_id=asset_id,
        upload_url=upload_url,
        upload_headers=headers,
        s3_key=s3_key,
        expires_at=datetime.fromisoformat(expires_at),
    )


@router.post("/{asset_id}/confirm", response_model=AssetOut)
async def confirm_upload(
    asset_id: str, body: ConfirmUploadBody, user: dict = Depends(get_current_user)
) -> AssetOut:
    db = get_db()
    doc = await db.assets.find_one({"id": asset_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Asset not found"}},
        )
    if not s3_service.object_exists(doc["s3_key"]):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "asset.binary_missing", "message": "Upload not received yet"}},
        )
    update: dict = {
        "upload_status": UploadStatus.uploaded.value,
        "size_bytes": s3_service.object_size(doc["s3_key"]),
        "updated_at": utc_now(),
    }
    if body.duration_sec is not None:
        update["duration_sec"] = body.duration_sec
    if body.width is not None:
        update["width"] = body.width
    if body.height is not None:
        update["height"] = body.height
    await db.assets.update_one({"id": asset_id}, {"$set": update})
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
    flt: dict = {"user_id": user["id"]}
    if kind:
        flt["kind"] = kind.value
    if project_id:
        flt["project_id"] = project_id
    if tag:
        flt["tags"] = tag
    if q:
        flt["filename"] = {"$regex": q, "$options": "i"}
    cursor = db.assets.find(flt, {"_id": 0}).sort("created_at", -1).limit(limit + 1)
    docs = await cursor.to_list(limit + 1)
    has_more = len(docs) > limit
    docs = docs[:limit]
    return AssetListOut(items=[_to_out(d) for d in docs], has_more=has_more)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: str, user: dict = Depends(get_current_user)) -> AssetOut:
    db = get_db()
    doc = await db.assets.find_one({"id": asset_id, "user_id": user["id"]}, {"_id": 0})
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
    s3_service.delete_object(doc["s3_key"])
    await db.assets.delete_one({"id": asset_id})
    return {"ok": True}


# ---------- Stub storage HTTP endpoints (replace with S3 in prod) ----------
# Path-style URL: /api/v1/_stub-storage/<full/s3/key>
# PUT writes the binary, GET streams it back. Public (signed via URL in prod).
stub_router = APIRouter(prefix="/_stub-storage", tags=["stub-storage"])


@stub_router.put("/{s3_key:path}")
async def stub_put(s3_key: str, request: Request) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail={"error": {"code": "upload.empty", "message": "Empty body"}})
    written = s3_service.write_object(s3_key, body)
    return {"ok": True, "bytes": written}


@stub_router.get("/{s3_key:path}")
async def stub_get(s3_key: str) -> Response:
    p: Path = s3_service.stream_path(s3_key)
    if not p.is_file():
        raise HTTPException(status_code=404, detail={"error": {"code": "asset.not_found", "message": "Object not found"}})
    return FileResponse(p)
