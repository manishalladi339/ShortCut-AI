"""User data deletion for account-closure and privacy requests."""
from __future__ import annotations

import asyncio

from db.mongo import get_db
from services.storage import get_storage


USER_SCOPED_COLLECTIONS = (
    "sessions",
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
)


async def delete_user_account(user_id: str) -> dict:
    db = get_db()

    # Delete durable media first. If storage deletion fails, leave the DB/user
    # intact so the operation can be retried without orphaning inaccessible data.
    deleted_objects = await asyncio.to_thread(
        get_storage().delete_prefix,
        f"users/{user_id}/",
    )

    deleted_docs = 0
    for name in USER_SCOPED_COLLECTIONS:
        result = await db[name].delete_many({"user_id": user_id})
        deleted_docs += int(result.deleted_count)

    await db.password_resets.delete_many({"user_id": user_id})
    await db.rate_limits.delete_many({"key": user_id})
    user_result = await db.users.delete_one({"id": user_id})
    return {
        "ok": bool(user_result.deleted_count),
        "deleted_objects": deleted_objects,
        "deleted_documents": deleted_docs,
    }
