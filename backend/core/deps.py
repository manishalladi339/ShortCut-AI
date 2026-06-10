"""FastAPI dependencies."""
from fastapi import Header, HTTPException, status
from jwt import PyJWTError

from core.security import decode_token
from db.mongo import get_db


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Extract Bearer JWT, decode, fetch user. Raises 401 on any failure."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth.token_missing", "message": "Bearer token required"}},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
        if payload.get("kind") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "auth.invalid_token", "message": "Invalid token kind"}},
            )
        user_id = payload["sub"]
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth.token_expired", "message": str(e)}},
        ) from e

    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth.user_not_found", "message": "User no longer exists"}},
        )
    return user
