"""Ensure indexes on startup."""
from db.mongo import get_db


async def _ensure_partial_unique(db, collection: str, field: str) -> None:
    """Drop any existing index on `field` and recreate as partial-on-string.

    `sparse=True` does NOT skip docs where the field is null; it only skips
    docs where the field is absent. Multiple users with `google_id=null`
    therefore collided. The partial filter scopes uniqueness to actual values.
    """
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
    # users
    await db.users.create_index("email", unique=True)
    await _ensure_partial_unique(db, "users", "google_id")
    await db.users.create_index("subscription_tier")
    # sessions
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("refresh_token_hash", unique=True)
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    # projects
    await db.projects.create_index("user_id")
    await db.projects.create_index([("user_id", 1), ("archived", 1), ("updated_at", -1)])
    await db.projects.create_index("status")
    # assets
    await db.assets.create_index("user_id")
    await db.assets.create_index("project_id")
    await db.assets.create_index([("user_id", 1), ("kind", 1)])
    await db.assets.create_index("s3_key", unique=True)
    # audit logs
    await db.audit_logs.create_index("user_id")
    await db.audit_logs.create_index("action")
    await db.audit_logs.create_index([("created_at", -1)])
