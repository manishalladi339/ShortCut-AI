"""Project CRUD router."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.common import ProjectStatus
from models.project import ProjectCreate, ProjectListOut, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_out(doc: dict) -> ProjectOut:
    return ProjectOut(**{k: v for k, v in doc.items() if k != "_id"})


def _new_project_doc(user_id: str, body: ProjectCreate) -> dict:
    now = utc_now()
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": body.title.strip(),
        "description": body.description,
        "content_type": body.content_type.value,
        "creation_mode": body.creation_mode.value,
        "status": ProjectStatus.draft.value,
        "desired_style": body.desired_style.value if body.desired_style else None,
        "target_platforms": [p.value for p in body.target_platforms],
        "prompt": body.prompt,
        "primary_asset_id": None,
        "output_clip_ids": [],
        "output_thumbnail_ids": [],
        "current_ai_job_id": None,
        "archived": False,
        "created_at": now,
        "updated_at": now,
    }


@router.get("", response_model=ProjectListOut)
async def list_projects(
    archived: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> ProjectListOut:
    db = get_db()
    cursor = (
        db.projects.find(
            {"user_id": user["id"], "archived": archived},
            {"_id": 0},
        )
        .sort("updated_at", -1)
        .limit(limit + 1)
    )
    docs = await cursor.to_list(limit + 1)
    has_more = len(docs) > limit
    docs = docs[:limit]
    return ProjectListOut(items=[_to_out(d) for d in docs], has_more=has_more)


@router.get("/recent", response_model=list[ProjectOut])
async def recent(user: dict = Depends(get_current_user)) -> list[ProjectOut]:
    db = get_db()
    docs = (
        await db.projects.find({"user_id": user["id"], "archived": False}, {"_id": 0})
        .sort("updated_at", -1)
        .limit(10)
        .to_list(10)
    )
    return [_to_out(d) for d in docs]


@router.get("/continue-editing", response_model=list[ProjectOut])
async def continue_editing(user: dict = Depends(get_current_user)) -> list[ProjectOut]:
    db = get_db()
    docs = (
        await db.projects.find(
            {
                "user_id": user["id"],
                "archived": False,
                "status": {"$in": [ProjectStatus.draft.value, ProjectStatus.processing.value]},
            },
            {"_id": 0},
        )
        .sort("updated_at", -1)
        .limit(5)
        .to_list(5)
    )
    return [_to_out(d) for d in docs]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)) -> ProjectOut:
    db = get_db()
    # quota check
    limit = user.get("monthly_project_limit", 3)
    count = user.get("monthly_project_count", 0)
    if limit != -1 and count >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "error": {
                    "code": "quota.exceeded",
                    "message": f"Free tier limit of {limit} projects/month reached",
                }
            },
        )
    doc = _new_project_doc(user["id"], body)
    await db.projects.insert_one(doc)
    await db.users.update_one(
        {"id": user["id"]}, {"$inc": {"monthly_project_count": 1}, "$set": {"updated_at": utc_now()}}
    )
    return _to_out(doc)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, user: dict = Depends(get_current_user)) -> ProjectOut:
    db = get_db()
    doc = await db.projects.find_one({"id": project_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )
    return _to_out(doc)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str, body: ProjectUpdate, user: dict = Depends(get_current_user)
) -> ProjectOut:
    db = get_db()
    update: dict = {"updated_at": utc_now()}
    if body.title is not None:
        update["title"] = body.title.strip()
    if body.description is not None:
        update["description"] = body.description
    if body.desired_style is not None:
        update["desired_style"] = body.desired_style.value
    if body.target_platforms is not None:
        update["target_platforms"] = [p.value for p in body.target_platforms]
    if body.prompt is not None:
        update["prompt"] = body.prompt
    result = await db.projects.update_one(
        {"id": project_id, "user_id": user["id"]}, {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return _to_out(doc)


@router.post("/{project_id}/duplicate", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def duplicate_project(project_id: str, user: dict = Depends(get_current_user)) -> ProjectOut:
    db = get_db()
    src = await db.projects.find_one({"id": project_id, "user_id": user["id"]}, {"_id": 0})
    if not src:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )
    now = utc_now()
    copy = {
        **src,
        "id": str(uuid.uuid4()),
        "title": f"{src['title']} (Copy)",
        "status": ProjectStatus.draft.value,
        "output_clip_ids": [],
        "output_thumbnail_ids": [],
        "current_ai_job_id": None,
        "archived": False,
        "created_at": now,
        "updated_at": now,
    }
    await db.projects.insert_one(copy)
    return _to_out(copy)


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(project_id: str, user: dict = Depends(get_current_user)) -> ProjectOut:
    db = get_db()
    result = await db.projects.update_one(
        {"id": project_id, "user_id": user["id"]},
        {"$set": {"archived": True, "status": ProjectStatus.archived.value, "updated_at": utc_now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )
    doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return _to_out(doc)


@router.delete("/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    result = await db.projects.delete_one({"id": project_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource.not_found", "message": "Project not found"}},
        )
    # Cascade: unlink assets (keep them in library), delete linked clips/jobs (none yet in 2.1).
    await db.assets.update_many({"project_id": project_id}, {"$set": {"project_id": None}})
    return {"ok": True}
