"""ShortCut AI — FastAPI app entry."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from core.config import settings
from db.indexes import ensure_indexes
from db.mongo import close as close_mongo
from db.mongo import get_db
from routers.assets import local_storage_router
from routers.assets import router as assets_router
from routers.ai_planner import router as ai_planner_router
from routers.auth import router as auth_router
from routers.constrained_edits import router as constrained_edits_router
from routers.creator_memory import router as creator_memory_router
from routers.jobs import router as jobs_router
from routers.intelligence import router as intelligence_router
from routers.project_state import router as project_state_router
from routers.planner_feedback import router as planner_feedback_router
from routers.project_intelligence import router as project_intelligence_router
from routers.render import router as render_router
from routers.retrieval import router as retrieval_router
from routers.projects import router as projects_router
from routers.users import router as users_router
from services.storage import get_storage

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("shortcut")

app = FastAPI(title="ShortCut AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "request_failed request_id=%s method=%s path=%s elapsed_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request request_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    else:
        body = {"error": {"code": "http_error", "message": str(detail)}}
    body.setdefault("request_id", getattr(request.state, "request_id", None))
    return JSONResponse(status_code=exc.status_code, content=body)


api = APIRouter(prefix="/api")
api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(projects_router)
api_v1.include_router(creator_memory_router)
api_v1.include_router(project_state_router)
api_v1.include_router(project_intelligence_router)
api_v1.include_router(constrained_edits_router)
api_v1.include_router(ai_planner_router)
api_v1.include_router(planner_feedback_router)
api_v1.include_router(render_router)
api_v1.include_router(assets_router)
api_v1.include_router(intelligence_router)
api_v1.include_router(retrieval_router)
api_v1.include_router(jobs_router)

# Local-storage upload/download routes are intentionally unavailable in production.
if settings.ENVIRONMENT != "production":
    api_v1.include_router(local_storage_router)


@api.get("/")
async def root():
    return {
        "name": "ShortCut AI",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


async def _readiness() -> tuple[bool, dict]:
    checks: dict = {}
    ready = True

    try:
        await get_db().command("ping")
        checks["mongo"] = {"ok": True}
    except Exception as exc:
        ready = False
        checks["mongo"] = {
            "ok": False,
            "error": type(exc).__name__,
        }

    try:
        checks["storage"] = await asyncio.to_thread(get_storage().healthcheck)
    except Exception as exc:
        ready = False
        checks["storage"] = {
            "ok": False,
            "backend": settings.STORAGE_BACKEND,
            "error": type(exc).__name__,
        }

    return ready, checks


@api.get("/health")
@api_v1.get("/health")
@api.get("/live")
@api_v1.get("/live")
async def live():
    # Backward-compatible health route remains a process liveness check.
    return {"ok": True}


@api.get("/ready")
@api_v1.get("/ready")
async def ready():
    ok, checks = await _readiness()
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "ok": ok,
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        },
    )


app.include_router(api)
app.include_router(api_v1)


@app.on_event("startup")
async def on_startup() -> None:
    settings.validate_runtime()
    await ensure_indexes()
    logger.info(
        "ShortCut AI ready environment=%s storage=%s",
        settings.ENVIRONMENT,
        settings.STORAGE_BACKEND,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_mongo()
