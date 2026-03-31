"""Diagnostic router — connectivity test endpoints for all authenticated users."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ai_config import AIConfig
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.schemas.admin import (
    TestAIRequest,
    TestAIResponse,
    TestEmailRequest,
    TestEmailResponse,
    TestSpotifyResponse,
    TrackItem,
)
from app.services import crypto
from app.services.ai.base import AIProvider
from app.services.ai.claude import ClaudeAdapter
from app.services.ai.perplexity import PerplexityAdapter
from app.services.email_service import send_test_email
from app.services.music.spotify import SpotifyAdapter

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_ai_adapter(provider: str) -> AIProvider:
    if provider == "claude":
        return ClaudeAdapter()
    if provider == "perplexity":
        return PerplexityAdapter()
    raise ValueError(f"Unknown AI provider: {provider!r}")


# ── POST /api/admin/test-email ────────────────────────────────────────────────


@router.post("/test-email", response_model=TestEmailResponse)
async def test_email(
    body: TestEmailRequest,
    user: User = Depends(get_current_user),
) -> TestEmailResponse:
    """Send a test email to verify that the SMTP configuration is working."""
    await send_test_email(recipient=body.recipient)
    return TestEmailResponse(
        message=f"Test email sent to {body.recipient}",
        recipient=body.recipient,
    )


# ── POST /api/admin/test-spotify/{account_id} ─────────────────────────────────


@router.post(
    "/test-spotify/{account_id}",
    response_model=TestSpotifyResponse,
)
async def test_spotify(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestSpotifyResponse:
    """Fetch the 10 most recently played tracks for a Spotify account.

    The account must belong to the authenticated user.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Spotify account not found"
        )
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this Spotify account",
        )

    access_token = crypto.decrypt(account.encrypted_access_token)
    refresh_token = crypto.decrypt(account.encrypted_refresh_token)

    now = datetime.now(UTC)
    expires_at = account.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= now:
        adapter = SpotifyAdapter()
        access_token, new_refresh, new_expires = await adapter.refresh_token(refresh_token)
        account.encrypted_access_token = crypto.encrypt(access_token)
        account.encrypted_refresh_token = crypto.encrypt(new_refresh)
        account.token_expires_at = new_expires
        await db.commit()

    adapter = SpotifyAdapter()
    tracks = await adapter.get_recently_played(access_token, limit=10)

    return TestSpotifyResponse(
        account_id=account.id,
        display_name=account.display_name,
        tracks=[
            TrackItem(
                title=t.title,
                artist=t.artist,
                album=t.album,
                played_at=t.played_at.isoformat(),
            )
            for t in tracks
        ],
        count=len(tracks),
    )


# ── POST /api/admin/test-ai/{config_id} ──────────────────────────────────────


@router.post("/test-ai/{config_id}", response_model=TestAIResponse)
async def test_ai(
    config_id: uuid.UUID,
    body: TestAIRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestAIResponse:
    """Send a test prompt to the configured AI provider.

    The AI config must belong to the authenticated user.
    """
    result = await db.execute(select(AIConfig).where(AIConfig.id == config_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI config not found"
        )
    if config.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this AI config",
        )

    api_key = crypto.decrypt(config.encrypted_api_key)
    adapter = _get_ai_adapter(config.provider)
    ai_result = await adapter.analyse(
        api_key=api_key,
        prompt=body.prompt,
        track_list="(connectivity test — no tracks)",
    )

    return TestAIResponse(
        config_id=config.id,
        provider=config.provider,
        model=ai_result.model,
        input_tokens=ai_result.input_tokens,
        output_tokens=ai_result.output_tokens,
        text=ai_result.text,
    )
