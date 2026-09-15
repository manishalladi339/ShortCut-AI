"""Ensure indexes on startup."""
from db.mongo import get_db


async def _ensure_partial_unique(db, collection: str, field: str) -> None:
    info = await db[collection].index_information()
    name = f"{field}_1"
    if name in info:
        await db[collection].drop_index(name)
    await db[collection].create_index(
        field,
        unique=True,
        partialFilterExpression={field: {"$type": "string"}},
    )


async def ensure_indexes() -> None:
    db = get_db()

    await db.users.create_index("email", unique=True)
    await _ensure_partial_unique(db, "users", "google_id")
    await db.users.create_index("subscription_tier")

    await db.sessions.create_index("user_id")
    await db.sessions.create_index("refresh_token_hash", unique=True)
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)

    await db.projects.create_index("user_id")
    await db.projects.create_index([("user_id", 1), ("archived", 1), ("updated_at", -1)])
    await db.projects.create_index("status")

    await db.project_states.create_index("project_id", unique=True)
    await db.project_states.create_index([("user_id", 1), ("updated_at", -1)])
    await db.edit_operations.create_index([("project_id", 1), ("to_version", 1)], unique=True)
    await db.edit_operations.create_index([("user_id", 1), ("created_at", -1)])

    await db.assets.create_index("user_id")
    await db.assets.create_index("project_id")
    await db.assets.create_index([("user_id", 1), ("kind", 1)])
    await db.assets.create_index("storage_key", unique=True)
    await db.assets.create_index([("processing_status", 1), ("updated_at", -1)])

    await db.jobs.create_index([("type", 1), ("status", 1), ("created_at", 1)])
    await db.jobs.create_index([("user_id", 1), ("created_at", -1)])
    await db.jobs.create_index("asset_id")

    await db.audit_logs.create_index("user_id")
    await db.audit_logs.create_index("action")
    await db.audit_logs.create_index([("created_at", -1)])
