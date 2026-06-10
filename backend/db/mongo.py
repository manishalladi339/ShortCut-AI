"""Mongo client + db handle (singleton)."""
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import settings

_client: AsyncIOMotorClient | None = None
_db = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URL)
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()[settings.DB_NAME]
    return _db


async def close():
    global _client
    if _client is not None:
        _client.close()
        _client = None
