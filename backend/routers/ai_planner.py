"""AI edit-plan proposal endpoints.

Plans are proposals only. They never mutate ProjectState automatically.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user
from db.mongo import get_db
from models.ai_plan import AIEditPlanOut, ApplyAIEditPlanRequest, CreateAIEditPlanRequest
from models.project_state import ProjectStateOut
from services.ai_edit_planner import build_plan
from services.creator_memory import refresh_creator_memory
from services.apply_ai_plan import apply_plan
from services.music_ducking import apply_music_ducking_policy
from services.planner_evaluation import evaluate_plan

router = APIRouter(prefix="/projects", tags=["ai-planner"])


@router.post(
    "/{project_id}/ai-plans",
    response_model=AIEditPlanOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_edit_plan(
    project_id: str,
    body: CreateAIEditPlanRequest,
    user: dict = Depends(get_current_user),
) -> AIEditPlanOut:
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id, "user_id": user["id"], "archived": False},
        {"_id": 0},
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )

    state = await db.project_states.find_one(
        {"project_id": project_id, "user_id": user["id"]},
        {"_id": 0},
    )
    if not state:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "planner.state_not_initialized",
                    "message": "Open the project state before creating an AI edit plan",
                }
            },
        )

    plan = await build_plan(project=project, user_id=user["id"], state=state, body=body)
    apply_music_ducking_policy(plan, body)
    plan["evaluation"] = evaluate_plan(plan)
    await db.ai_edit_plans.insert_one(plan.copy())
    return AIEditPlanOut(**plan)


@router.get("/{project_id}/ai-plans", response_model=list[AIEditPlanOut])
async def list_ai_edit_plans(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> list[AIEditPlanOut]:
    docs = await (
        get_db().ai_edit_plans.find(
            {"project_id": project_id, "user_id": user["id"]},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .limit(50)
        .to_list(50)
    )
    return [AIEditPlanOut(**doc) for doc in docs]


@router.get("/{project_id}/ai-plans/{plan_id}", response_model=AIEditPlanOut)
async def get_ai_edit_plan(
    project_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
) -> AIEditPlanOut:
    doc = await get_db().ai_edit_plans.find_one(
        {"id": plan_id, "project_id": project_id, "user_id": user["id"]},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "planner.plan_not_found", "message": "AI edit plan not found"}},
        )
    return AIEditPlanOut(**doc)


@router.post(
    "/{project_id}/ai-plans/{plan_id}/apply",
    response_model=ProjectStateOut,
)
async def apply_ai_edit_plan(
    project_id: str,
    plan_id: str,
    body: ApplyAIEditPlanRequest,
    user: dict = Depends(get_current_user),
) -> ProjectStateOut:
    plan = await get_db().ai_edit_plans.find_one(
        {"id": plan_id, "project_id": project_id, "user_id": user["id"]},
        {"_id": 0},
    )
    if not plan:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "planner.plan_not_found", "message": "AI edit plan not found"}},
        )
    state = await apply_plan(
        plan=plan,
        user_id=user["id"],
        expected_version=body.expected_version,
        replace_existing_video_clips=body.replace_existing_video_clips,
        operation_ids=body.operation_ids,
    )
    await refresh_creator_memory(user_id=user["id"])
    return ProjectStateOut(**state)
