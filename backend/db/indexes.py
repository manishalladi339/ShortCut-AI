"""Ensure indexes on startup."""
from db.mongo import get_db


async def ensure_indexes() -> None:
    db = get_db()
    # users
    await db.users.create_index("email", unique=True)
    await db.users.create_index("google_id", unique=True, sparse=True)
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
