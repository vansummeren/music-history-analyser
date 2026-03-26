"""Spotify OAuth and account-management router."""
from __future__ import annotations

import secrets
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.spotify import SpotifyAccountRead, SpotifyLinkResponse, TrackRead
from app.services import crypto
from app.services.music.spotify import (
    SPOTIFY_SCOPES,
    SpotifyAdapter,
    exchange_code,
    fetch_spotify_user,
)

router = APIRouter(prefix="/api/spotify", tags=["spotify"])

_SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
_STATE_PREFIX = "spotify_state:"
_STATE_TTL = 600  # 10 minutes


# ── OAuth flow ────────────────────────────────────────────────────────────────


@router.post("/link", response_model=SpotifyLinkResponse)
async def link_spotify(
    user: User = Depends(get_current_user),
    redis: Any = Depends(get_redis),
) -> SpotifyLinkResponse:
    """Generate and return the Spotify OAuth authorisation URL.

    The caller (frontend) should redirect the user's browser to ``auth_url``.
    """
    state = secrets.token_hex(16)
    # Store user_id so the callback knows who is linking
    await redis.set(f"{_STATE_PREFIX}{state}", str(user.id), ex=_STATE_TTL)

    auth_url = (
        f"{_SPOTIFY_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={urllib.parse.quote(settings.spotify_client_id)}"
        f"&scope={urllib.parse.quote(SPOTIFY_SCOPES)}"
        f"&redirect_uri={urllib.parse.quote(settings.spotify_redirect_uri)}"
        f"&state={state}"
        f"&show_dialog=true"
    )
    return SpotifyLinkResponse(auth_url=auth_url)


@router.get("/callback")
async def spotify_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> RedirectResponse:
    """OAuth callback: exchange code → tokens, upsert SpotifyAccount, redirect."""
    # Validate state
    raw = await redis.get(f"{_STATE_PREFIX}{state}")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    await redis.delete(f"{_STATE_PREFIX}{state}")
    user_id = uuid.UUID(raw.decode() if isinstance(raw, bytes) else raw)

    # Exchange authorization code for tokens
    token_data = await exchange_code(code)
    access_token: str = token_data["access_token"]
    refresh_token: str = token_data["refresh_token"]
    expires_in: int = token_data.get("expires_in", 3600)
    scopes: str = token_data.get("scope", "")
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    # Fetch Spotify user profile
    spotify_user = await fetch_spotify_user(access_token)
    spotify_user_id: str = spotify_user["id"]
    display_name: str | None = spotify_user.get("display_name")
    email_list: list[dict[str, Any]] = spotify_user.get("emails", [])
    email: str | None = email_list[0].get("email") if email_list else spotify_user.get("email")

    # Encrypt tokens before storing
    enc_access = crypto.encrypt(access_token)
    enc_refresh = crypto.encrypt(refresh_token)

    # Upsert SpotifyAccount (one row per spotify_user_id)
    result = await db.execute(
        select(SpotifyAccount).where(SpotifyAccount.spotify_user_id == spotify_user_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        account = SpotifyAccount(
            user_id=user_id,
            spotify_user_id=spotify_user_id,
            display_name=display_name,
            email=email,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            token_expires_at=expires_at,
            scopes=scopes,
        )
        db.add(account)
    else:
        # Re-link: update tokens and ownership
        account.user_id = user_id
        account.display_name = display_name
        account.email = email
        account.encrypted_access_token = enc_access
        account.encrypted_refresh_token = enc_refresh
        account.token_expires_at = expires_at
        account.scopes = scopes
        account.updated_at = datetime.now(UTC)

    await db.commit()

    return RedirectResponse(f"{settings.frontend_url}/spotify")


# ── Account management ────────────────────────────────────────────────────────


@router.get("/accounts", response_model=list[SpotifyAccountRead])
async def list_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SpotifyAccount]:
    """Return all Spotify accounts linked to the authenticated user."""
    result = await db.execute(
        select(SpotifyAccount).where(SpotifyAccount.user_id == user.id)
    )
    return list(result.scalars().all())


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def unlink_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a linked Spotify account.  Returns 403 if the account is not owned by the user."""
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to unlink this account",
        )
    await db.delete(account)
    await db.commit()


@router.get("/accounts/{account_id}/history", response_model=list[TrackRead])
async def get_history(
    account_id: uuid.UUID,
    time_window: int = Query(default=7, ge=1, le=90, description="Days of history to fetch"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackRead]:
    """Return recent listening history for a linked Spotify account.

    *time_window* is the number of days back to retrieve (1–90, default 7).
    Token refresh is handled transparently when the stored token has expired.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this account",
        )

    # Decrypt and refresh token if needed
    access_token = crypto.decrypt(account.encrypted_access_token)
    refresh_token = crypto.decrypt(account.encrypted_refresh_token)

    now = datetime.now(UTC)
    # SQLite (used in tests) may return a naive datetime; treat it as UTC.
    expires_at = account.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        adapter = SpotifyAdapter()
        access_token, new_refresh, new_expires = await adapter.refresh_token(refresh_token)
        account.encrypted_access_token = crypto.encrypt(access_token)
        account.encrypted_refresh_token = crypto.encrypt(new_refresh)
        account.token_expires_at = new_expires
        account.updated_at = now
        await db.commit()

    after = now - timedelta(days=time_window)
    adapter = SpotifyAdapter()
    tracks = await adapter.get_recently_played(access_token, after=after, limit=50)

    return [
        TrackRead(
            title=t.title,
            artist=t.artist,
            album=t.album,
            played_at=t.played_at,
        )
        for t in tracks
    ]
