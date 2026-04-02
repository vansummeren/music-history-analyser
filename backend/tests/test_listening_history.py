"""Tests for Session 08 — Listening History (shadow DB, polling, play events)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listening_history import Album, Artist, PlayEvent, Track, TrackArtist
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.services import auth_service, crypto
from app.services.music.base import Album as AlbumDTO
from app.services.music.base import Artist as ArtistDTO
from app.services.music.base import Track as TrackDTO
from tests.conftest import FakeRedis

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "history-sub",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="user@example.com", display_name="Test"
    )
    token = auth_service.create_access_token(user.id)
    return user, token


async def _make_account(
    db: AsyncSession,
    user: User,
    *,
    spotify_user_id: str = "spotify-history-user",
) -> SpotifyAccount:
    account = SpotifyAccount(
        user_id=user.id,
        spotify_user_id=spotify_user_id,
        display_name="History User",
        email="history@example.com",
        encrypted_access_token=crypto.encrypt("access-token"),
        encrypted_refresh_token=crypto.encrypt("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes="user-read-recently-played user-top-read",
        poll_interval_minutes=60,
        polling_enabled=True,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


def _make_track_dto(
    *,
    external_id: str = "track-001",
    title: str = "Test Song",
    artist_id: str = "artist-001",
    artist_name: str = "Test Artist",
    album_id: str = "album-001",
    album_title: str = "Test Album",
    played_at: datetime | None = None,
) -> TrackDTO:
    if played_at is None:
        played_at = datetime.now(UTC) - timedelta(minutes=30)
    return TrackDTO(
        title=title,
        artist=artist_name,
        album=album_title,
        played_at=played_at,
        external_id=external_id,
        provider="spotify",
        album_obj=AlbumDTO(external_id=album_id, title=album_title, provider="spotify"),
        artist_objs=[ArtistDTO(external_id=artist_id, name=artist_name, provider="spotify")],
        duration_ms=200_000,
        media_type="track",
    )


# ── 1. SpotifyAccount model — polling fields ───────────────────────────────────


@pytest.mark.asyncio
async def test_spotify_account_default_poll_config(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Newly created accounts should have sensible polling defaults."""
    user, _ = await _make_user(db_session, fake_redis, sub="sub-defaults")
    account = await _make_account(db_session, user)

    assert account.poll_interval_minutes == 60
    assert account.polling_enabled is True
    assert account.last_polled_at is None


# ── 2. history_service.poll_account ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_account_stores_play_events(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """poll_account should upsert tracks/artists/albums and create PlayEvent rows."""
    from app.services.history_service import poll_account

    user, _ = await _make_user(db_session, fake_redis, sub="sub-poll")
    account = await _make_account(db_session, user)

    track_dto = _make_track_dto()

    with patch(
        "app.services.history_service.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=[track_dto]),
    ):
        new_count = await poll_account(db_session, account.id)

    assert new_count == 1

    # Verify Artist persisted
    artist = await db_session.get(Artist, ("spotify", "artist-001"))
    assert artist is not None
    assert artist.name == "Test Artist"

    # Verify Album persisted
    album = await db_session.get(Album, ("spotify", "album-001"))
    assert album is not None
    assert album.title == "Test Album"

    # Verify Track persisted
    track = await db_session.get(Track, ("spotify", "track-001"))
    assert track is not None
    assert track.title == "Test Song"
    assert track.media_type == "track"

    # Verify TrackArtist junction
    link = await db_session.get(TrackArtist, ("spotify", "track-001", "spotify", "artist-001"))
    assert link is not None

    # Verify PlayEvent created
    result = await db_session.execute(
        select(PlayEvent).where(PlayEvent.streaming_account_id == account.id)
    )
    events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].track_external_id == "track-001"


@pytest.mark.asyncio
async def test_poll_account_deduplication(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Polling the same track with the same played_at twice should only insert one event."""
    from app.services.history_service import poll_account

    user, _ = await _make_user(db_session, fake_redis, sub="sub-dedup")
    account = await _make_account(db_session, user)

    played_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    track_dto = _make_track_dto(played_at=played_at)

    with patch(
        "app.services.history_service.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=[track_dto]),
    ):
        count1 = await poll_account(db_session, account.id)
        count2 = await poll_account(db_session, account.id)

    assert count1 == 1
    assert count2 == 0  # duplicate — not inserted again

    result = await db_session.execute(
        select(PlayEvent).where(PlayEvent.streaming_account_id == account.id)
    )
    assert len(list(result.scalars().all())) == 1


@pytest.mark.asyncio
async def test_poll_account_updates_last_polled_at(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """last_polled_at should be updated to the most recent played_at after polling."""
    from app.services.history_service import poll_account

    user, _ = await _make_user(db_session, fake_redis, sub="sub-cursor")
    account = await _make_account(db_session, user)
    assert account.last_polled_at is None

    played_at = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    track_dto = _make_track_dto(played_at=played_at)

    with patch(
        "app.services.history_service.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=[track_dto]),
    ):
        await poll_account(db_session, account.id)

    await db_session.refresh(account)
    assert account.last_polled_at is not None
    lp = account.last_polled_at
    if lp.tzinfo is None:
        lp = lp.replace(tzinfo=UTC)
    assert lp == played_at


@pytest.mark.asyncio
async def test_poll_account_disabled_skips(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Accounts with polling_enabled=False should be skipped."""
    from app.services.history_service import poll_account

    user, _ = await _make_user(db_session, fake_redis, sub="sub-disabled")
    account = await _make_account(db_session, user)
    account.polling_enabled = False
    await db_session.commit()

    track_dto = _make_track_dto()
    mock_get = AsyncMock(return_value=[track_dto])

    with patch(
        "app.services.history_service.SpotifyAdapter.get_recently_played",
        mock_get,
    ):
        count = await poll_account(db_session, account.id)

    assert count == 0
    mock_get.assert_not_called()


# ── 3. PATCH /api/spotify/accounts/{id} — poll config update ────────────────


@pytest.mark.asyncio
async def test_update_poll_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-patch")
    account = await _make_account(db_session, user)

    resp = await client.patch(
        f"/api/spotify/accounts/{account.id}",
        json={"poll_interval_minutes": 30, "polling_enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["poll_interval_minutes"] == 30
    assert data["polling_enabled"] is False


@pytest.mark.asyncio
async def test_update_poll_config_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-patch")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-patch")
    account = await _make_account(db_session, owner)

    resp = await client.patch(
        f"/api/spotify/accounts/{account.id}",
        json={"poll_interval_minutes": 15},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_poll_config_invalid_interval(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """poll_interval_minutes must be between 1 and 1440."""
    user, token = await _make_user(db_session, fake_redis, sub="sub-invalid")
    account = await _make_account(db_session, user)

    resp = await client.patch(
        f"/api/spotify/accounts/{account.id}",
        json={"poll_interval_minutes": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ── 4. POST /api/spotify/accounts/{id}/poll — manual trigger ────────────────


@pytest.mark.asyncio
async def test_trigger_poll_accepted(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-trigger")
    account = await _make_account(db_session, user)

    with patch("app.tasks.celery_app.celery_app.send_task") as mock_send:
        resp = await client.post(
            f"/api/spotify/accounts/{account.id}/poll",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["queued"] is True
    mock_send.assert_called_once_with("poll_history_for_account", args=[str(account.id)])


@pytest.mark.asyncio
async def test_trigger_poll_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-trigger")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-trigger")
    account = await _make_account(db_session, owner)

    resp = await client.post(
        f"/api/spotify/accounts/{account.id}/poll",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


# ── 5. GET /api/spotify/accounts/{id}/play-events ────────────────────────────


@pytest.mark.asyncio
async def test_get_play_events_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-events-empty")
    account = await _make_account(db_session, user)

    resp = await client.get(
        f"/api/spotify/accounts/{account.id}/play-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_play_events_returns_stored_history(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    from app.services.history_service import poll_account

    user, token = await _make_user(db_session, fake_redis, sub="sub-events-list")
    account = await _make_account(db_session, user)

    track_dto = _make_track_dto(
        played_at=datetime(2026, 3, 15, 8, 0, 0, tzinfo=UTC)
    )
    with patch(
        "app.services.history_service.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=[track_dto]),
    ):
        await poll_account(db_session, account.id)

    resp = await client.get(
        f"/api/spotify/accounts/{account.id}/play-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["track_external_id"] == "track-001"
    assert events[0]["track_title"] == "Test Song"
    assert events[0]["track_artist"] == "Test Artist"
    assert events[0]["track_album"] == "Test Album"


@pytest.mark.asyncio
async def test_get_play_events_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-events")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-events")
    account = await _make_account(db_session, owner)

    resp = await client.get(
        f"/api/spotify/accounts/{account.id}/play-events",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_play_events_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """limit and offset parameters should be honoured."""
    from app.services.history_service import poll_account

    user, token = await _make_user(db_session, fake_redis, sub="sub-events-page")
    account = await _make_account(db_session, user)

    # Insert 3 play events with different tracks and times
    track_dtos = [
        _make_track_dto(
            external_id=f"track-p{i:02d}",
            artist_id=f"artist-p{i:02d}",
            album_id=f"album-p{i:02d}",
            played_at=datetime(2026, 3, 1, i, 0, 0, tzinfo=UTC),
        )
        for i in range(3)
    ]

    with patch(
        "app.services.history_service.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=track_dtos),
    ):
        await poll_account(db_session, account.id)

    # Ask for 2 events
    resp = await client.get(
        f"/api/spotify/accounts/{account.id}/play-events?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Ask for the remaining 1
    resp = await client.get(
        f"/api/spotify/accounts/{account.id}/play-events?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── 6. SpotifyAdapter top tracks / top artists ───────────────────────────────


@pytest.mark.asyncio
async def test_spotify_adapter_get_top_tracks() -> None:
    """SpotifyAdapter.get_top_tracks should parse the Spotify response."""
    from app.services.music.spotify import SpotifyAdapter

    mock_response_data = {
        "items": [
            {
                "id": "6rqhFgbbKwnb9MLmUQDhG6",
                "name": "Blinding Lights",
                "artists": [{"id": "1Xyo4u8uXC1ZmMpatF05PJ", "name": "The Weeknd"}],
                "album": {"id": "4yP0hdKOZPNshxUOjY0cZj", "name": "After Hours"},
                "popularity": 95,
                "duration_ms": 200_040,
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response_data
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        adapter = SpotifyAdapter()
        top_tracks = await adapter.get_top_tracks("test-token", limit=1)

    assert len(top_tracks) == 1
    assert top_tracks[0].external_id == "6rqhFgbbKwnb9MLmUQDhG6"
    assert top_tracks[0].title == "Blinding Lights"
    assert top_tracks[0].artist == "The Weeknd"
    assert top_tracks[0].album == "After Hours"
    assert top_tracks[0].popularity == 95


@pytest.mark.asyncio
async def test_spotify_adapter_get_top_artists() -> None:
    """SpotifyAdapter.get_top_artists should parse the Spotify response."""
    from app.services.music.spotify import SpotifyAdapter

    mock_response_data = {
        "items": [
            {
                "id": "1Xyo4u8uXC1ZmMpatF05PJ",
                "name": "The Weeknd",
                "genres": ["canadian pop", "pop"],
                "popularity": 97,
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response_data
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        adapter = SpotifyAdapter()
        top_artists = await adapter.get_top_artists("test-token", limit=1)

    assert len(top_artists) == 1
    assert top_artists[0].external_id == "1Xyo4u8uXC1ZmMpatF05PJ"
    assert top_artists[0].name == "The Weeknd"
    assert "pop" in top_artists[0].genres
    assert top_artists[0].popularity == 97


# ── 8. SpotifyRateLimitError — HTTP 429 handling ─────────────────────────────


def _make_429_response(retry_after: str | None = "30") -> MagicMock:
    """Build a mock httpx.Response for HTTP 429."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    headers: dict[str, str] = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    mock_resp.headers = headers
    return mock_resp


def _make_mock_client(mock_resp: MagicMock) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_get_recently_played_raises_rate_limit_error() -> None:
    """get_recently_played should raise SpotifyRateLimitError on HTTP 429."""
    from app.services.music.spotify import SpotifyAdapter, SpotifyRateLimitError

    mock_resp = _make_429_response(retry_after="42")
    mock_client = _make_mock_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        adapter = SpotifyAdapter()
        with pytest.raises(SpotifyRateLimitError) as exc_info:
            await adapter.get_recently_played("test-token")

    assert exc_info.value.retry_after == 42


@pytest.mark.asyncio
async def test_get_recently_played_rate_limit_missing_header() -> None:
    """SpotifyRateLimitError.retry_after defaults to 0 when Retry-After is absent."""
    from app.services.music.spotify import SpotifyAdapter, SpotifyRateLimitError

    mock_resp = _make_429_response(retry_after=None)
    mock_client = _make_mock_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        adapter = SpotifyAdapter()
        with pytest.raises(SpotifyRateLimitError) as exc_info:
            await adapter.get_recently_played("test-token")

    assert exc_info.value.retry_after == 0


@pytest.mark.asyncio
async def test_get_top_tracks_raises_rate_limit_error() -> None:
    """get_top_tracks should raise SpotifyRateLimitError on HTTP 429."""
    from app.services.music.spotify import SpotifyAdapter, SpotifyRateLimitError

    mock_resp = _make_429_response(retry_after="15")
    mock_client = _make_mock_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        adapter = SpotifyAdapter()
        with pytest.raises(SpotifyRateLimitError) as exc_info:
            await adapter.get_top_tracks("test-token")

    assert exc_info.value.retry_after == 15


@pytest.mark.asyncio
async def test_get_top_artists_raises_rate_limit_error() -> None:
    """get_top_artists should raise SpotifyRateLimitError on HTTP 429."""
    from app.services.music.spotify import SpotifyAdapter, SpotifyRateLimitError

    mock_resp = _make_429_response(retry_after="60")
    mock_client = _make_mock_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        adapter = SpotifyAdapter()
        with pytest.raises(SpotifyRateLimitError) as exc_info:
            await adapter.get_top_artists("test-token")

    assert exc_info.value.retry_after == 60



@pytest.mark.asyncio
async def test_account_read_includes_poll_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-schema")
    await _make_account(db_session, user)

    resp = await client.get(
        "/api/spotify/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "poll_interval_minutes" in data[0]
    assert "polling_enabled" in data[0]
    assert "last_polled_at" in data[0]
    assert data[0]["poll_interval_minutes"] == 60
    assert data[0]["polling_enabled"] is True
