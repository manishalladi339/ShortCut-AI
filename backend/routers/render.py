"""Render-plan API.

This endpoint compiles a pinned, deterministic plan. Actual FFmpeg rendering is
a subsequent worker milestone.
"""
from fastapi import APIRouter, Depends, Query

from core.deps import get_current_user
from models.render_plan import RenderPlan
from services.render_plan import compile_render_plan

router = APIRouter(prefix="/projects", tags=["render"])


@router.post("/{project_id}/render-plan", response_model=RenderPlan)
async def create_render_plan(
    project_id: str,
    sequence_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> RenderPlan:
    return await compile_render_plan(
        project_id=project_id,
        user_id=user["id"],
        sequence_id=sequence_id,
    )
