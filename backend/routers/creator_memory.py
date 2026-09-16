"""Creator Memory API."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models.creator_memory import CreatorMemoryOut
from services.creator_memory import get_creator_memory, refresh_creator_memory

router = APIRouter(prefix="/users/me/creator-memory", tags=["creator-memory"])


@router.get("", response_model=CreatorMemoryOut)
async def read_creator_memory(
    user: dict = Depends(get_current_user),
) -> CreatorMemoryOut:
    return CreatorMemoryOut(**(await get_creator_memory(user_id=user["id"])))


@router.post("/refresh", response_model=CreatorMemoryOut)
async def rebuild_creator_memory(
    user: dict = Depends(get_current_user),
) -> CreatorMemoryOut:
    return CreatorMemoryOut(**(await refresh_creator_memory(user_id=user["id"])))
