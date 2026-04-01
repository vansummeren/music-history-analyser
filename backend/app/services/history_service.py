"""History service — upserts listening-history data into the normalised DB.

This service is called both from the Celery polling task and directly from the
API when a manual "poll now" action is triggered.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listening_history import Album, Artist, PlayEvent, Track, TrackArtist
from app.models.spotify_account import SpotifyAccount
from app.services import crypto
from app.services.music.base import Track as TrackDTO
from app.services.music.spotify import SpotifyAdapter

logger = logging.getLogger(__name__)

_PROVIDER = "spotify"


# ── Upsert helpers ─────────────────────────────────────────────────────────────


async def _upsert_artist(db: AsyncSession, external_id: str, name: str) -> None:
    """Insert the artist if it does not yet exist; update the name if it does."""
    existing = await db.get(Artist, (_PROVIDER, external_id))
    if existing is None:
        db.add(
            Artist(
                provider=_PROVIDER,
                external_id=external_id,
                name=name,
            )
        )
    else:
        existing.name = name
        existing.updated_at = datetime.now(UTC)


async def _upsert_album(db: AsyncSession, external_id: str, title: str) -> None:
    """Insert the album if it does not yet exist; update the title if it does."""
    existing = await db.get(Album, (_PROVIDER, external_id))
    if existing is None:
        db.add(
            Album(
                provider=_PROVIDER,
                external_id=external_id,
                title=title,
            )
        )
    else:
        existing.title = title
        existing.updated_at = datetime.now(UTC)


async def _upsert_track(db: AsyncSession, track_dto: TrackDTO) -> None:
    """Insert/update a track and its album + artists into the DB."""
    # Album (if present)
    if track_dto.album_obj and track_dto.album_obj.external_id:
        await _upsert_album(
            db,
            external_id=track_dto.album_obj.external_id,
            title=track_dto.album_obj.title,
        )

    # Track
    existing_track = await db.get(Track, (_PROVIDER, track_dto.external_id))
    if existing_track is None:
        db.add(
            Track(
                provider=_PROVIDER,
                external_id=track_dto.external_id,
                title=track_dto.title,
                album_provider=(
                    _PROVIDER
                    if track_dto.album_obj and track_dto.album_obj.external_id
                    else None
                ),
                album_external_id=(
                    track_dto.album_obj.external_id
                    if track_dto.album_obj and track_dto.album_obj.external_id
                    else None
                ),
                duration_ms=track_dto.duration_ms,
                media_type=track_dto.media_type,
            )
        )
    else:
        existing_track.title = track_dto.title
        existing_track.duration_ms = track_dto.duration_ms
        existing_track.updated_at = datetime.now(UTC)

    # Artists + junction rows
    for artist_dto in track_dto.artist_objs:
        if not artist_dto.external_id:
            continue
        await _upsert_artist(db, external_id=artist_dto.external_id, name=artist_dto.name)

        existing_link = await db.get(
            TrackArtist,
            (_PROVIDER, track_dto.external_id, _PROVIDER, artist_dto.external_id),
        )
        if existing_link is None:
            db.add(
                TrackArtist(
                    track_provider=_PROVIDER,
                    track_external_id=track_dto.external_id,
                    artist_provider=_PROVIDER,
                    artist_external_id=artist_dto.external_id,
                )
            )


async def _insert_play_event(
    db: AsyncSession,
    streaming_account_id: uuid.UUID,
    track_external_id: str,
    played_at: datetime,
) -> bool:
    """Insert a play event; return True if inserted, False if it already exists."""
    # Check for existing event to avoid the unique-constraint exception
    result = await db.execute(
        select(PlayEvent).where(
            PlayEvent.streaming_account_id == streaming_account_id,
            PlayEvent.track_provider == _PROVIDER,
            PlayEvent.track_external_id == track_external_id,
            PlayEvent.played_at == played_at,
        )
    )
    if result.scalar_one_or_none() is not None:
        return False

    db.add(
        PlayEvent(
            streaming_account_id=streaming_account_id,
            track_provider=_PROVIDER,
            track_external_id=track_external_id,
            played_at=played_at,
        )
    )
    return True


# ── Main polling function ──────────────────────────────────────────────────────


async def poll_account(db: AsyncSession, account_id: uuid.UUID) -> int:
    """Poll new listening history for *account_id* and persist it.

    Fetches recently played tracks from Spotify using the account's
    ``last_polled_at`` timestamp as the ``after`` cursor so that only new
    events are imported.  All upserted entities are flushed within one
    transaction.

    Returns the number of new ``PlayEvent`` rows created.

    Access control: the caller is responsible for verifying account ownership
    before calling this function.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise ValueError(f"SpotifyAccount {account_id} not found")

    if not account.polling_enabled:
        logger.info("Polling disabled for account %s — skipping", account_id)
        return 0

    # Decrypt and refresh token if needed
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
        account.updated_at = now
        logger.info("Token refreshed for account %s", account_id)

    # Use last_polled_at as cursor (None → fetch the last 50 tracks with no filter)
    after = account.last_polled_at
    if after is not None and after.tzinfo is None:
        after = after.replace(tzinfo=UTC)

    adapter = SpotifyAdapter()
    tracks = await adapter.get_recently_played(access_token, after=after, limit=50)

    new_events = 0
    for track_dto in tracks:
        if not track_dto.external_id:
            logger.debug("Skipping track with no external_id: %r", track_dto.title)
            continue

        await _upsert_track(db, track_dto)
        inserted = await _insert_play_event(
            db,
            streaming_account_id=account_id,
            track_external_id=track_dto.external_id,
            played_at=track_dto.played_at,
        )
        if inserted:
            new_events += 1

    # Advance the cursor to the most recently played track
    if tracks:
        most_recent = max(t.played_at for t in tracks)
        if most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=UTC)
        # Only advance; never roll back the cursor
        if account.last_polled_at is None or most_recent > account.last_polled_at.replace(
            tzinfo=UTC
        ):
            account.last_polled_at = most_recent

    account.updated_at = now
    await db.commit()

    logger.info(
        "Polled account %s — %d track(s) fetched, %d new event(s) stored",
        account_id, len(tracks), new_events,
    )
    return new_events


# ── Query helpers ──────────────────────────────────────────────────────────────


async def get_accounts_due_for_poll(db: AsyncSession) -> list[SpotifyAccount]:
    """Return all accounts whose next scheduled poll is due now or overdue."""
    from sqlalchemy import func, or_

    result = await db.execute(
        select(SpotifyAccount).where(
            SpotifyAccount.polling_enabled.is_(True),
            or_(
                SpotifyAccount.last_polled_at.is_(None),
                # next_poll = last_polled_at + poll_interval_minutes * 60 seconds
                func.now()
                >= SpotifyAccount.last_polled_at
                + func.make_interval(0, 0, 0, 0, 0, SpotifyAccount.poll_interval_minutes),
            ),
        )
    )
    return list(result.scalars().all())
