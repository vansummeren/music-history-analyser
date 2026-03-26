"""Users router."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me")
async def users_me(user: User = Depends(get_current_user)) -> UserRead:
    """Return the profile of the currently authenticated user."""
    return UserRead.model_validate(user)
