"""Human feedback loop for planner evaluation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.planner_feedback import (
    PlannerFeedbackOut,
    PlannerFeedbackRequest,
    PlannerMetricsOut,
)

router = APIRouter(prefix="/projects", tags=["planner-evaluation"])


@router.post(
    "/{project_id}/ai-plans/{plan_id}/feedback",
    response_model=PlannerFeedbackOut,
)
async def submit_plan_feedback(
    project_id: str,
    plan_id: str,
    body: PlannerFeedbackRequest,
    user: dict = Depends(get_current_user),
) -> PlannerFeedbackOut:
    db = get_db()
    plan = await db.ai_edit_plans.find_one(
        {"id": plan_id, "project_id": project_id, "user_id": user["id"]},
        {"_id": 0, "id": 1},
    )
    if not plan:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "planner.plan_not_found",
                    "message": "AI edit plan not found",
                }
            },
        )

    now = utc_now()
    existing = await db.ai_plan_feedback.find_one(
        {"plan_id": plan_id, "user_id": user["id"]},
        {"_id": 0},
    )
    created_at = existing.get("created_at") if existing else now
    doc = {
        "plan_id": plan_id,
        "project_id": project_id,
        "user_id": user["id"],
        "outcome": body.outcome,
        "notes": body.notes,
        "created_at": created_at,
        "updated_at": now,
    }
    await db.ai_plan_feedback.update_one(
        {"plan_id": plan_id, "user_id": user["id"]},
        {"$set": doc},
        upsert=True,
    )
    await db.ai_edit_plans.update_one(
        {"id": plan_id, "user_id": user["id"]},
        {
            "$set": {
                "feedback_outcome": body.outcome,
                "updated_at": now,
            }
        },
    )
    return PlannerFeedbackOut(**doc)


@router.get(
    "/{project_id}/ai-plans/metrics",
    response_model=PlannerMetricsOut,
)
async def get_planner_metrics(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> PlannerMetricsOut:
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id, "user_id": user["id"]},
        {"_id": 0, "id": 1},
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "resource.not_found",
                    "message": "Project not found",
                }
            },
        )

    pipeline = [
        {"$match": {"project_id": project_id, "user_id": user["id"]}},
        {"$group": {"_id": "$outcome", "count": {"$sum": 1}}},
    ]
    rows = await db.ai_plan_feedback.aggregate(pipeline).to_list(10)
    counts = {row["_id"]: row["count"] for row in rows}
    accepted = int(counts.get("accepted", 0))
    rejected = int(counts.get("rejected", 0))
    modified = int(counts.get("modified", 0))
    total = accepted + rejected + modified
    rate = accepted / total if total else 0.0
    return PlannerMetricsOut(
        total_feedback=total,
        accepted=accepted,
        rejected=rejected,
        modified=modified,
        acceptance_rate=round(rate, 4),
    )
