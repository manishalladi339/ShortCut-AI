"""Authentication: signup, login, Google (Emergent), refresh, me, password reset."""

from __future__ import annotations

import asyncio
import logging
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from core.config import settings
from core.deps import get_current_user
from core.security import (
    decode_token,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    utc_now,
    verify_password,
)
from db.mongo import get_db
from services.mail import send_reset_email
from models.common import AuthProvider, SubscriptionTier
from models.user import (
    AuthResponse,
    ForgotPasswordBody,
    GoogleAuthBody,
    LoginBody,
    RefreshBody,
    ResetPasswordBody,
    SignupBody,
    TokenPair,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_public(user_doc: dict) -> UserPublic:
    return UserPublic(
        id=user_doc["id"],
        email=user_doc["email"],
        name=user_doc["name"],
        avatar_url=user_doc.get("avatar_url"),
        role=user_doc.get("role", "user"),
        auth_provider=user_doc.get("auth_provider", AuthProvider.email),
        subscription_tier=user_doc.get("subscription_tier", SubscriptionTier.free),
        onboarding_complete=user_doc.get("onboarding_complete", False),
        user_type=user_doc.get("user_type"),
        niche=user_doc.get("niche", []),
        created_at=user_doc["created_at"],
    )


async def _persist_session(user_id: str, refresh_token: str) -> None:
    db = get_db()
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    await db.sessions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "refresh_token_hash": token_hash,
            "expires_at": utc_now() + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
            "revoked": False,
            "created_at": utc_now(),
        }
    )


async def _audit(
    user_id: str | None, action: str, metadata: dict | None = None
) -> None:
    db = get_db()
    await db.audit_logs.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": action,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }
    )


async def _new_tokens(user_id: str) -> TokenPair:
    access = issue_access_token(user_id)
    refresh = issue_refresh_token(user_id)
    await _persist_session(user_id, refresh)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post(
    "/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def signup(body: SignupBody) -> AuthResponse:
    db = get_db()
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}, {"_id": 0, "id": 1}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "auth.email_taken",
                    "message": "Email already registered",
                }
            },
        )
    user_doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(body.password),
        "auth_provider": AuthProvider.email.value,
        "google_id": None,
        "name": body.name.strip(),
        "avatar_url": None,
        "role": "user",
        "subscription_tier": SubscriptionTier.free.value,
        "subscription_status": "active",
        "monthly_project_count": 0,
        "monthly_project_limit": 3,
        "onboarding_complete": False,
        "user_type": None,
        "niche": [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    await db.users.insert_one(user_doc)
    tokens = await _new_tokens(user_doc["id"])
    await _audit(user_doc["id"], "auth.signup")
    return AuthResponse(
        user=_user_to_public(user_doc),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginBody) -> AuthResponse:
    db = get_db()
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "auth.invalid_credentials",
                    "message": "Invalid email or password",
                }
            },
        )
    if not verify_password(body.password, user["password_hash"]):
        await _audit(user["id"], "auth.login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "auth.invalid_credentials",
                    "message": "Invalid email or password",
                }
            },
        )
    tokens = await _new_tokens(user["id"])
    await _audit(user["id"], "auth.login")
    return AuthResponse(
        user=_user_to_public(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(body: GoogleAuthBody) -> AuthResponse:
    """Exchange Emergent-issued session_token for our own JWT.

    We verify the session_token against Emergent's session-data endpoint,
    upsert the user by email, then issue our own access/refresh JWT pair.
    """
    db = get_db()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                settings.EMERGENT_AUTH_SESSION_URL,
                headers={"X-Session-ID": body.session_token},
            )
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "auth.google_unreachable", "message": str(e)}},
        )
    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "auth.google_invalid",
                    "message": "Session verification failed",
                }
            },
        )
    try:
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid response")
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "auth.google_invalid",
                    "message": "Session verification failed",
                }
            },
        )
    google_email = (data.get("email") or "").lower().strip()
    google_id = data.get("id")
    name = data.get("name") or google_email.split("@")[0]
    picture = data.get("picture")
    if not google_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "auth.google_missing_email",
                    "message": "Google did not return an email",
                }
            },
        )

    existing = await db.users.find_one({"email": google_email}, {"_id": 0})
    if existing:
        update = {
            "google_id": google_id,
            "updated_at": utc_now(),
        }
        if not existing.get("avatar_url") and picture:
            update["avatar_url"] = picture
        # Promote provider to "both" if user already had email auth, else "google".
        if existing.get("password_hash"):
            update["auth_provider"] = AuthProvider.both.value
        else:
            update["auth_provider"] = AuthProvider.google.value
        await db.users.update_one({"id": existing["id"]}, {"$set": update})
        existing.update(update)
        user_doc = existing
    else:
        user_doc = {
            "id": str(uuid.uuid4()),
            "email": google_email,
            "password_hash": None,
            "auth_provider": AuthProvider.google.value,
            "google_id": google_id,
            "name": name,
            "avatar_url": picture,
            "role": "user",
            "subscription_tier": SubscriptionTier.free.value,
            "subscription_status": "active",
            "monthly_project_count": 0,
            "monthly_project_limit": 3,
            "onboarding_complete": False,
            "user_type": None,
            "niche": [],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await db.users.insert_one(user_doc)

    tokens = await _new_tokens(user_doc["id"])
    await _audit(user_doc["id"], "auth.google_login")
    return AuthResponse(
        user=_user_to_public(user_doc),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(body: RefreshBody) -> TokenPair:
    db = get_db()
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("kind") != "refresh":
            raise ValueError("not_a_refresh_token")
        user_id = payload["sub"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "auth.token_expired", "message": str(e)}},
        )
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    session = await db.sessions.find_one_and_update(
        {
            "refresh_token_hash": token_hash,
            "revoked": False,
            "user_id": user_id,
            "expires_at": {"$gt": utc_now()},
        },
        {"$set": {"revoked": True}},
        projection={"_id": 0},
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "auth.session_revoked",
                    "message": "Session no longer valid",
                }
            },
        )
    # Rotate: revoke old session, issue new.
    await db.sessions.update_one(
        {"refresh_token_hash": token_hash}, {"$set": {"revoked": True}}
    )
    tokens = await _new_tokens(user_id)
    return tokens


@router.post("/logout")
async def logout(body: RefreshBody, _user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    await db.sessions.update_one(
        {"refresh_token_hash": token_hash}, {"$set": {"revoked": True}}
    )
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordBody) -> dict:
    """Always returns 200 to avoid email enumeration. Stores a reset token if user exists."""
    if not settings.SMTP_HOST:
        raise HTTPException(
            status_code=503, detail="Password reset email is not configured"
        )
    db = get_db()
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_resets.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "expires_at": utc_now() + timedelta(hours=1),
                "used": False,
                "created_at": utc_now(),
            }
        )
        try:
            await asyncio.to_thread(send_reset_email, email, token)
        except Exception:
            # Do not disclose account existence through delivery failures.
            logging.getLogger("shortcut.mail").error("Password reset delivery failed")
        await _audit(user["id"], "auth.password_reset_requested")
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordBody) -> dict:
    db = get_db()
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    rec = await db.password_resets.find_one_and_update(
        {"token_hash": token_hash, "used": False, "expires_at": {"$gt": utc_now()}},
        {"$set": {"used": True}},
        projection={"_id": 0},
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "auth.invalid_reset_token",
                    "message": "Invalid or used token",
                }
            },
        )
    exp = rec["expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "auth.expired_reset_token",
                    "message": "Token expired",
                }
            },
        )
    await db.users.update_one(
        {"id": rec["user_id"]},
        {
            "$set": {
                "password_hash": hash_password(body.new_password),
                "updated_at": utc_now(),
            }
        },
    )
    await db.password_resets.update_one(
        {"token_hash": token_hash}, {"$set": {"used": True}}
    )
    # Revoke all sessions for safety.
    await db.sessions.update_many(
        {"user_id": rec["user_id"]}, {"$set": {"revoked": True}}
    )
    await _audit(rec["user_id"], "auth.password_reset_completed")
    return {"ok": True}


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)) -> UserPublic:
    return _user_to_public(user)
