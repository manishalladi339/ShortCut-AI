"""User profile router."""
from fastapi import APIRouter, Depends

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.user import UpdateProfileBody, UserPublic
from routers.auth import _user_to_public

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_me(user: dict = Depends(get_current_user)) -> UserPublic:
    return _user_to_public(user)


@router.patch("/me", response_model=UserPublic)
async def update_me(body: UpdateProfileBody, user: dict = Depends(get_current_user)) -> UserPublic:
    db = get_db()
    update: dict = {"updated_at": utc_now()}
    if body.name is not None:
        update["name"] = body.name.strip()
    if body.avatar_url is not None:
        update["avatar_url"] = body.avatar_url
    if body.user_type is not None:
        update["user_type"] = body.user_type
    if body.niche is not None:
        update["niche"] = body.niche
    if body.onboarding_complete is not None:
        update["onboarding_complete"] = body.onboarding_complete
    await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return _user_to_public(fresh)
