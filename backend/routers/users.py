"""User profile and account lifecycle router."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.user import UpdateProfileBody, UserPublic
from routers.auth import _user_to_public
from services.storage import get_storage

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_me(user: dict = Depends(get_current_user)) -> UserPublic:
    return _user_to_public(user)


@router.patch("/me", response_model=UserPublic)
async def update_me(body: UpdateProfileBody, user: dict = Depends(get_current_user)) -> UserPublic:
    db = get_db()
    update: dict = {"updated_at": utc_now()}
    if body.name is not None:
        update["name"] = body.name.strip()
    if body.avatar_url is not None:
        update["avatar_url"] = body.avatar_url
    if body.user_type is not None:
        update["user_type"] = body.user_type
    if body.niche is not None:
        update["niche"] = body.niche
    if body.onboarding_complete is not None:
        update["onboarding_complete"] = body.onboarding_complete
    await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return _user_to_public(fresh)


def _collect_storage_keys(value) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        key = value.get("storage_key")
        if isinstance(key, str) and key:
            keys.add(key)
        for child in value.values():
            keys.update(_collect_storage_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_collect_storage_keys(child))
    return keys


@router.delete("/me")
async def delete_me(user: dict = Depends(get_current_user)) -> dict:
    """Permanently delete the signed-in user's account and owned application data."""
    db = get_db()
    user_id = user["id"]

    assets = await db.assets.find(
        {"user_id": user_id}, {"_id": 0, "storage_key": 1, "derivatives": 1}
    ).to_list(None)
    exports = await db.exports.find(
        {"user_id": user_id}, {"_id": 0, "storage_key": 1}
    ).to_list(None)

    keys: set[str] = set()
    for asset in assets:
        if asset.get("storage_key"):
            keys.add(asset["storage_key"])
        keys.update(_collect_storage_keys(asset.get("derivatives") or {}))
    for export in exports:
        if export.get("storage_key"):
            keys.add(export["storage_key"])

    storage = get_storage()
    failed: list[str] = []
    for key in sorted(keys):
        try:
            await asyncio.to_thread(storage.delete, key)
        except Exception:
            failed.append(key)

    if failed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "account.storage_cleanup_failed",
                    "message": "Account deletion could not safely remove all stored media. Retry shortly.",
                }
            },
        )

    collections = [
        "sessions",
        "password_resets",
        "projects",
        "project_states",
        "project_state_versions",
        "edit_operations",
        "assets",
        "jobs",
        "exports",
        "media_intelligence",
        "project_intelligence",
        "creator_memories",
        "ai_constrained_edit_proposals",
        "ai_edit_plans",
        "ai_plan_feedback",
        "audit_logs",
    ]
    for collection in collections:
        await db[collection].delete_many({"user_id": user_id})

    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count != 1:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Account not found"}},
        )
    return {"ok": True}
