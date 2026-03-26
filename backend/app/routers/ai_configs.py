"""AI configuration management router."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ai_config import AIConfig
from app.models.user import User
from app.schemas.ai import AIConfigCreate, AIConfigRead
from app.services import crypto

router = APIRouter(prefix="/api/ai-configs", tags=["ai-configs"])


@router.post("", response_model=AIConfigRead, status_code=status.HTTP_201_CREATED)
async def create_ai_config(
    body: AIConfigCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIConfig:
    """Store a new AI provider configuration with an encrypted API key."""
    config = AIConfig(
        user_id=user.id,
        provider=body.provider,
        display_name=body.display_name,
        encrypted_api_key=crypto.encrypt(body.api_key),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.get("", response_model=list[AIConfigRead])
async def list_ai_configs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AIConfig]:
    """Return all AI configurations belonging to the authenticated user."""
    result = await db.execute(select(AIConfig).where(AIConfig.user_id == user.id))
    return list(result.scalars().all())


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_ai_config(
    config_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an AI configuration. Returns 403 if not owned by the user."""
    config = await db.get(AIConfig, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    if config.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this config",
        )
    await db.delete(config)
    await db.commit()
