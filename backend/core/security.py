"""Security helpers: bcrypt password hashing + JWT issuance / validation."""
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt

from core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _issue_token(sub: str, kind: Literal["access", "refresh"], extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    if kind == "access":
        exp = now + timedelta(minutes=settings.JWT_ACCESS_TTL_MIN)
    else:
        exp = now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    payload = {"sub": sub, "kind": kind, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def issue_access_token(user_id: str) -> str:
    return _issue_token(user_id, "access")


def issue_refresh_token(user_id: str) -> str:
    return _issue_token(user_id, "refresh")


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError subclass on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()
