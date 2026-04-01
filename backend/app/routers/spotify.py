"""Spotify OAuth and account-management router."""
from __future__ import annotations

import logging
import secrets
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.listening_history import PlayEvent, Track
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.spotify import (
    PlayEventRead,
    SpotifyAccountPollUpdate,
    SpotifyAccountRead,
    SpotifyLinkResponse,
    TrackRead,
)
from app.services import crypto
from app.services.music.spotify import (
    SPOTIFY_SCOPES,
    SpotifyAdapter,
    exchange_code,
    fetch_spotify_user,
)

logger = logging.getLogger(__name__)

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
    state: str,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """OAuth callback: exchange code → tokens, upsert SpotifyAccount, redirect.

    Handles both the success case (``code`` present) and the error case
    (``error`` present, e.g. user denied the authorisation on Spotify).
    """
    # Always validate the state first so only legitimate OAuth flows can
    # consume it (prevents state-exhaustion / CSRF replay attacks).
    raw = await redis.get(f"{_STATE_PREFIX}{state}")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    await redis.delete(f"{_STATE_PREFIX}{state}")
    user_id = uuid.UUID(raw.decode() if isinstance(raw, bytes) else raw)

    # Spotify sent back an error (e.g. access_denied) — redirect to the
    # frontend so it can show a user-friendly message.
    if error is not None or code is None:
        # Map to a fixed literal so no user-supplied data reaches the redirect URL.
        if error == "access_denied":
            safe_error = "access_denied"
        elif error == "server_error":
            safe_error = "server_error"
        elif error == "temporarily_unavailable":
            safe_error = "temporarily_unavailable"
        elif error == "state_mismatch":
            safe_error = "state_mismatch"
        else:
            safe_error = "unknown"
        return RedirectResponse(
            f"{settings.frontend_url}/spotify?error={safe_error}"
        )

    # Exchange authorization code for tokens
    try:
        token_data = await exchange_code(code)
    except httpx.HTTPStatusError as exc:
        logger.warning("Spotify token exchange failed: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/spotify?error=token_exchange_failed")
    except httpx.RequestError as exc:
        logger.warning("Spotify token exchange request error: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/spotify?error=token_exchange_failed")

    access_token: str = token_data["access_token"]
    # Spotify omits refresh_token on re-authorization of an already-approved app.
    # For new accounts it is always present; for re-links we fall back to the
    # existing stored token below.
    refresh_token: str | None = token_data.get("refresh_token")
    expires_in: int = token_data.get("expires_in", 3600)
    scopes: str = token_data.get("scope", "")
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    # Fetch Spotify user profile
    try:
        spotify_user = await fetch_spotify_user(access_token)
    except httpx.HTTPStatusError as exc:
        logger.warning("Spotify profile fetch failed: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/spotify?error=profile_fetch_failed")
    except httpx.RequestError as exc:
        logger.warning("Spotify profile fetch request error: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/spotify?error=profile_fetch_failed")
    spotify_user_id: str = spotify_user["id"]
    display_name: str | None = spotify_user.get("display_name")
    email_list: list[dict[str, Any]] = spotify_user.get("emails", [])
    email: str | None = email_list[0].get("email") if email_list else spotify_user.get("email")

    # Encrypt access token; refresh token is encrypted only when present.
    enc_access = crypto.encrypt(access_token)

    # Upsert SpotifyAccount (one row per spotify_user_id)
    result = await db.execute(
        select(SpotifyAccount).where(SpotifyAccount.spotify_user_id == spotify_user_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        # Brand-new Spotify account — refresh_token is required.
        # Spotify only issues refresh_token on the first authorization; if the
        # account was previously linked and then unlinked, the user must revoke
        # the app in Spotify settings (https://www.spotify.com/account/apps) and
        # re-authorize to obtain a new refresh token.
        if refresh_token is None:
            logger.warning(
                "Spotify did not return a refresh token for new account '%s'; "
                "user may need to revoke the app in Spotify settings",
                spotify_user_id,
            )
            return RedirectResponse(
                f"{settings.frontend_url}/spotify?error=no_refresh_token"
            )
        account = SpotifyAccount(
            user_id=user_id,
            spotify_user_id=spotify_user_id,
            display_name=display_name,
            email=email,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=crypto.encrypt(refresh_token),
            token_expires_at=expires_at,
            scopes=scopes,
        )
        db.add(account)
    else:
        # Re-link: update tokens and ownership.
        # Keep the stored refresh_token when Spotify doesn't issue a new one.
        account.user_id = user_id
        account.display_name = display_name
        account.email = email
        account.encrypted_access_token = enc_access
        if refresh_token is not None:
            account.encrypted_refresh_token = crypto.encrypt(refresh_token)
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


# ── Polling configuration ─────────────────────────────────────────────────────


@router.patch("/accounts/{account_id}", response_model=SpotifyAccountRead)
async def update_poll_config(
    account_id: uuid.UUID,
    payload: SpotifyAccountPollUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpotifyAccount:
    """Update the polling configuration for a linked Spotify account.

    Accepts ``poll_interval_minutes`` (1–1440) and/or ``polling_enabled``
    to configure how often automatic history polling runs for this account.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this account",
        )

    if payload.poll_interval_minutes is not None:
        account.poll_interval_minutes = payload.poll_interval_minutes
    if payload.polling_enabled is not None:
        account.polling_enabled = payload.polling_enabled
    account.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(account)
    return account


@router.post(
    "/accounts/{account_id}/poll",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict[str, object],
)
async def trigger_poll(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Manually trigger a history poll for a linked Spotify account.

    Dispatches a Celery task and returns immediately.  The task runs
    asynchronously — check the account's ``last_polled_at`` field to
    confirm completion.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to poll this account",
        )

    from app.tasks.celery_app import celery_app as _celery

    _celery.send_task("poll_history_for_account", args=[str(account_id)])
    logger.info("Manual poll dispatched for account %s by user %s", account_id, user.id)
    return {"queued": True, "account_id": str(account_id)}


# ── Play events (shadow DB history) ──────────────────────────────────────────


@router.get("/accounts/{account_id}/play-events", response_model=list[PlayEventRead])
async def get_play_events(
    account_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of events"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlayEventRead]:
    """Return stored play events for a linked Spotify account from the shadow DB.

    Results are ordered by ``played_at`` descending (most recent first).
    Access is restricted to the account owner.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this account",
        )

    result = await db.execute(
        select(PlayEvent)
        .where(PlayEvent.streaming_account_id == account_id)
        .order_by(PlayEvent.played_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = list(result.scalars().all())

    if not events:
        return []

    # ── Batch-load all related entities to avoid N+1 queries ─────────────────
    from app.models.listening_history import Album, Artist, TrackArtist

    # Collect unique track keys from this page
    track_keys = list({(e.track_provider, e.track_external_id) for e in events})

    # 1. Fetch all tracks in one query (IN over composite values via OR)
    from sqlalchemy import and_, or_

    tracks_result = await db.execute(
        select(Track).where(
            or_(
                and_(
                    Track.provider == provider,
                    Track.external_id == ext_id,
                )
                for provider, ext_id in track_keys
            )
        )
    )
    track_map: dict[tuple[str, str], Track] = {
        (t.provider, t.external_id): t for t in tracks_result.scalars().all()
    }

    # 2. Fetch all TrackArtist junction rows for these tracks in one query
    track_artists_result = await db.execute(
        select(TrackArtist).where(
            or_(
                and_(
                    TrackArtist.track_provider == provider,
                    TrackArtist.track_external_id == ext_id,
                )
                for provider, ext_id in track_keys
            )
        )
    )
    all_links = list(track_artists_result.scalars().all())

    # 3. Fetch all artists referenced by those junction rows in one query
    artist_keys = list({(link.artist_provider, link.artist_external_id) for link in all_links})
    artist_map: dict[tuple[str, str], Artist] = {}
    if artist_keys:
        artists_result = await db.execute(
            select(Artist).where(
                or_(
                    and_(
                        Artist.provider == provider,
                        Artist.external_id == ext_id,
                    )
                    for provider, ext_id in artist_keys
                )
            )
        )
        artist_map = {
            (a.provider, a.external_id): a for a in artists_result.scalars().all()
        }

    # Build a mapping: track_key → sorted artist names
    track_artist_names: dict[tuple[str, str], list[str]] = {k: [] for k in track_keys}
    for link in all_links:
        artist = artist_map.get((link.artist_provider, link.artist_external_id))
        if artist:
            track_artist_names[(link.track_provider, link.track_external_id)].append(artist.name)

    # 4. Fetch all albums for the tracks in one query
    album_keys = list(
        {
            (t.album_provider, t.album_external_id)
            for t in track_map.values()
            if t.album_provider and t.album_external_id
        }
    )
    album_map: dict[tuple[str, str], Album] = {}
    if album_keys:
        albums_result = await db.execute(
            select(Album).where(
                or_(
                    and_(
                        Album.provider == provider,
                        Album.external_id == ext_id,
                    )
                    for provider, ext_id in album_keys
                )
            )
        )
        album_map = {
            (a.provider, a.external_id): a for a in albums_result.scalars().all()
        }

    # ── Assemble the response ─────────────────────────────────────────────────
    output: list[PlayEventRead] = []
    for event in events:
        key = (event.track_provider, event.track_external_id)
        track = track_map.get(key)

        track_title = track.title if track else ""
        track_artist = ", ".join(track_artist_names.get(key, []))
        track_album = ""
        if track and track.album_provider and track.album_external_id:
            album = album_map.get((track.album_provider, track.album_external_id))
            if album:
                track_album = album.title

        output.append(
            PlayEventRead(
                id=event.id,
                streaming_account_id=event.streaming_account_id,
                track_provider=event.track_provider,
                track_external_id=event.track_external_id,
                played_at=event.played_at,
                created_at=event.created_at,
                track_title=track_title,
                track_artist=track_artist,
                track_album=track_album,
            )
        )

    return output
