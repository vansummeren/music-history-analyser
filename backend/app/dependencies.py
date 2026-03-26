"""FastAPI dependency helpers."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.redis_client import get_redis
from app.services import auth_service

# auto_error=False so we can return 401 (not 403) when the header is missing.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> User:
    """Validate the Bearer token and return the authenticated User.

    Raises HTTP 401 when the token is missing, malformed, expired, or revoked.
    """
    credentials: HTTPAuthorizationCredentials | None = await _bearer(request)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_id: uuid.UUID | None = auth_service.verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    if await auth_service.is_token_revoked(token, redis):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def require_role(role: str) -> Any:
    """Return a FastAPI dependency that enforces a minimum role.

    Usage::

        @router.get("/admin-only")
        async def admin(user: User = Depends(require_role("admin"))):
            ...
    """

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
