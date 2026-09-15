"""ShortCut AI — FastAPI app entry."""
import logging

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from db.indexes import ensure_indexes
from db.mongo import close as close_mongo
from routers.assets import local_storage_router
from routers.assets import router as assets_router
from routers.ai_planner import router as ai_planner_router
from routers.auth import router as auth_router
from routers.jobs import router as jobs_router
from routers.intelligence import router as intelligence_router
from routers.project_state import router as project_state_router
from routers.render import router as render_router
from routers.retrieval import router as retrieval_router
from routers.projects import router as projects_router
from routers.users import router as users_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut")

app = FastAPI(title="ShortCut AI", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    else:
        body = {"error": {"code": "http_error", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


api = APIRouter(prefix="/api")
api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(projects_router)
api_v1.include_router(project_state_router)
api_v1.include_router(ai_planner_router)
api_v1.include_router(render_router)
api_v1.include_router(assets_router)
api_v1.include_router(intelligence_router)
api_v1.include_router(retrieval_router)
api_v1.include_router(jobs_router)
api_v1.include_router(local_storage_router)


@api.get("/")
async def root():
    return {"name": "ShortCut AI", "version": "0.6.0", "docs": "/docs"}


@api.get("/health")
async def health():
    return {"ok": True}


@api_v1.get("/health")
async def health_v1():
    return {"ok": True}


app.include_router(api)
app.include_router(api_v1)


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_indexes()
    logger.info("ShortCut AI ready")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_mongo()
