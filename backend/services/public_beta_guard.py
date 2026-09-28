"""Public-beta abuse and cost guards.

The guard is intentionally enforced before expensive AI/render work is queued.
Rate-limit state is Mongo-backed so multiple API replicas share the same counters.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import timedelta

from pymongo import ReturnDocument

from core.config import settings
from core.security import decode_token, utc_now
from db.mongo import get_db


@dataclass(frozen=True)
class GuardRejection:
    status_code: int
    code: str
    message: str
    retry_after: int


@dataclass(frozen=True)
class RatePolicy:
    scope: str
    limit: int


def route_policy(method: str, path: str) -> RatePolicy | None:
    if method != "POST":
        return None
    if path in {
        "/api/v1/auth/signup",
        "/api/v1/auth/login",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/refresh",
    }:
        return RatePolicy("auth", settings.RATE_LIMIT_AUTH_PER_MIN)
    if path == "/api/v1/assets/presign-upload":
        return RatePolicy("upload", settings.RATE_LIMIT_UPLOAD_PER_MIN)
    if re.fullmatch(r"/api/v1/assets/[^/]+/analyze", path):
        return RatePolicy("ai", settings.RATE_LIMIT_AI_PER_MIN)
    if re.fullmatch(r"/api/v1/projects/[^/]+/exports", path):
        return RatePolicy("render", settings.RATE_LIMIT_RENDER_PER_MIN)
    if re.fullmatch(r"/api/v1/projects/[^/]+/(ai-plans|constrained-edits)", path):
        return RatePolicy("ai", settings.RATE_LIMIT_AI_PER_MIN)
    if re.fullmatch(r"/api/v1/projects/[^/]+/exports/[^/]+/qa-fix-proposal", path):
        return RatePolicy("ai", settings.RATE_LIMIT_AI_PER_MIN)
    return None


def _client_key(request) -> str:
    client = getattr(request, "client", None)
    return (getattr(client, "host", None) or "unknown")[:128]


def _access_user_id(request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if payload.get("kind") != "access":
        return None
    user_id = payload.get("sub")
    return str(user_id) if user_id else None


def _seconds_until_utc_day_reset() -> int:
    now = utc_now()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


async def _rate_limit(request, policy: RatePolicy) -> GuardRejection | None:
    window = 60
    now = utc_now()
    bucket = int(time.time() // window)
    key = f"{policy.scope}:{_client_key(request)}:{bucket}"
    doc = await get_db().rate_limits.find_one_and_update(
        {"_id": key},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {
                "scope": policy.scope,
                "created_at": now,
                "expires_at": now + timedelta(seconds=window * 2),
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    count = int((doc or {}).get("count", 0))
    if count <= policy.limit:
        return None
    return GuardRejection(
        status_code=429,
        code="rate_limit.exceeded",
        message="Too many requests. Please try again shortly.",
        retry_after=max(1, window - int(time.time() % window)),
    )


async def _free_user(user_id: str) -> bool:
    user = await get_db().users.find_one(
        {"id": user_id}, {"_id": 0, "subscription_tier": 1}
    )
    return bool(user) and user.get("subscription_tier", "free") == "free"


async def _usage_limit(request, user_id: str) -> GuardRejection | None:
    if not await _free_user(user_id):
        return None

    path = request.url.path
    if request.method != "POST":
        return None

    now = utc_now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    reset = _seconds_until_utc_day_reset()
    db = get_db()

    if re.fullmatch(r"/api/v1/assets/[^/]+/analyze", path):
        count = await db.jobs.count_documents(
            {
                "user_id": user_id,
                "type": "media_intelligence",
                "created_at": {"$gte": day_start},
            }
        )
        if count >= settings.MAX_DAILY_INTELLIGENCE_JOBS_FREE:
            return GuardRejection(
                429,
                "usage.daily_intelligence_limit",
                "Daily media-analysis limit reached for the free beta.",
                reset,
            )

    if re.fullmatch(r"/api/v1/projects/[^/]+/exports", path):
        active = await db.jobs.count_documents(
            {
                "user_id": user_id,
                "type": "render_export",
                "status": {"$in": ["queued", "running"]},
            }
        )
        if active >= settings.MAX_CONCURRENT_RENDER_JOBS_FREE:
            return GuardRejection(
                429,
                "usage.concurrent_render_limit",
                "Too many renders are already queued or running.",
                60,
            )
        count = await db.jobs.count_documents(
            {
                "user_id": user_id,
                "type": "render_export",
                "created_at": {"$gte": day_start},
            }
        )
        if count >= settings.MAX_DAILY_RENDER_JOBS_FREE:
            return GuardRejection(
                429,
                "usage.daily_render_limit",
                "Daily render limit reached for the free beta.",
                reset,
            )

    collection = None
    if re.fullmatch(r"/api/v1/projects/[^/]+/ai-plans", path):
        collection = db.ai_edit_plans
    elif re.fullmatch(r"/api/v1/projects/[^/]+/constrained-edits", path):
        collection = db.ai_constrained_edit_proposals
    elif re.fullmatch(r"/api/v1/projects/[^/]+/exports/[^/]+/qa-fix-proposal", path):
        collection = db.ai_constrained_edit_proposals

    if collection is not None:
        count = await collection.count_documents(
            {"user_id": user_id, "created_at": {"$gte": day_start}}
        )
        if count >= settings.MAX_DAILY_AI_REQUESTS_FREE:
            return GuardRejection(
                429,
                "usage.daily_ai_limit",
                "Daily AI-edit request limit reached for the free beta.",
                reset,
            )
    return None


async def check_public_beta_guard(request) -> GuardRejection | None:
    if not settings.RATE_LIMIT_ENABLED:
        return None

    policy = route_policy(request.method, request.url.path)
    if policy is not None:
        rejected = await _rate_limit(request, policy)
        if rejected is not None:
            return rejected

    user_id = _access_user_id(request)
    if user_id:
        return await _usage_limit(request, user_id)
    return None
