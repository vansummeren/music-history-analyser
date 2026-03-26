"""Tests for Session 03 — Spotify Integration."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.services import auth_service, crypto
from tests.conftest import FakeRedis

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "test-sub",
) -> tuple[User, str]:
    """Create a user and return (user, access_token)."""
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="user@example.com", display_name="Test User"
    )
    token = auth_service.create_access_token(user.id)
    return user, token


async def _make_spotify_account(
    db: AsyncSession,
    user: User,
    *,
    spotify_user_id: str = "spotify-abc",
    expires_at: datetime | None = None,
) -> SpotifyAccount:
    """Create a SpotifyAccount linked to *user*."""
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=1)
    account = SpotifyAccount(
        user_id=user.id,
        spotify_user_id=spotify_user_id,
        display_name="Spotify User",
        email="spotify@example.com",
        encrypted_access_token=crypto.encrypt("access-token"),
        encrypted_refresh_token=crypto.encrypt("refresh-token"),
        token_expires_at=expires_at,
        scopes="user-read-recently-played",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


# ── 1. POST /api/spotify/link returns an auth URL ────────────────────────────


@pytest.mark.asyncio
async def test_link_returns_auth_url(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis)

    resp = await client.post(
        "/api/spotify/link", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    assert "accounts.spotify.com/authorize" in data["auth_url"]
    assert "response_type=code" in data["auth_url"]


@pytest.mark.asyncio
async def test_link_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/spotify/link")
    assert resp.status_code == 401


# ── 2. GET /api/spotify/callback — success stores account ────────────────────


@pytest.mark.asyncio
async def test_callback_stores_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    from sqlalchemy import select

    user, _ = await _make_user(db_session, fake_redis)
    state = "test-state-xyz"
    await fake_redis.set(f"spotify_state:{state}", str(user.id))

    token_response: dict[str, Any] = {
        "access_token": "sp-access",
        "refresh_token": "sp-refresh",
        "expires_in": 3600,
        "scope": "user-read-recently-played",
    }
    spotify_profile: dict[str, Any] = {
        "id": "spotify-user-1",
        "display_name": "Test Spotify",
        "email": "spotify@example.com",
        "emails": [{"email": "spotify@example.com"}],
    }

    with (
        patch(
            "app.routers.spotify.exchange_code",
            AsyncMock(return_value=token_response),
        ),
        patch(
            "app.routers.spotify.fetch_spotify_user",
            AsyncMock(return_value=spotify_profile),
        ),
    ):
        resp = await client.get(
            f"/api/spotify/callback?code=authcode&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)
    assert "/spotify" in resp.headers["location"]

    result = await db_session.execute(
        select(SpotifyAccount).where(SpotifyAccount.spotify_user_id == "spotify-user-1")
    )
    account = result.scalar_one_or_none()
    assert account is not None
    assert account.user_id == user.id
    # Tokens must be stored encrypted (not plaintext)
    assert account.encrypted_access_token != "sp-access"
    assert crypto.decrypt(account.encrypted_access_token) == "sp-access"


@pytest.mark.asyncio
async def test_callback_invalid_state_returns_400(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/spotify/callback?code=x&state=bad-state")
    assert resp.status_code == 400


# ── 3. GET /api/spotify/accounts ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_accounts_returns_linked(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis)
    await _make_spotify_account(db_session, user)

    resp = await client.get(
        "/api/spotify/accounts", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["spotify_user_id"] == "spotify-abc"


@pytest.mark.asyncio
async def test_list_accounts_empty_for_new_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis)

    resp = await client.get(
        "/api/spotify/accounts", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_accounts_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/spotify/accounts")
    assert resp.status_code == 401


# ── 4. DELETE /api/spotify/accounts/{id} ─────────────────────────────────────


@pytest.mark.asyncio
async def test_unlink_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    from sqlalchemy import select

    user, token = await _make_user(db_session, fake_redis)
    account = await _make_spotify_account(db_session, user)

    resp = await client.delete(
        f"/api/spotify/accounts/{account.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    result = await db_session.execute(
        select(SpotifyAccount).where(SpotifyAccount.id == account.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_unlink_account_forbidden_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-sub")
    other, other_token = await _make_user(db_session, fake_redis, sub="other-sub")
    account = await _make_spotify_account(db_session, owner)

    resp = await client.delete(
        f"/api/spotify/accounts/{account.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unlink_account_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis)

    resp = await client.delete(
        f"/api/spotify/accounts/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── 5. GET /api/spotify/accounts/{id}/history ────────────────────────────────


@pytest.mark.asyncio
async def test_history_returns_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    from app.services.music.base import Track

    user, token = await _make_user(db_session, fake_redis)
    account = await _make_spotify_account(db_session, user)

    tracks = [
        Track(
            title="Song A",
            artist="Artist A",
            album="Album A",
            played_at=datetime.now(UTC) - timedelta(hours=1),
        ),
        Track(
            title="Song B",
            artist="Artist B",
            album="Album B",
            played_at=datetime.now(UTC) - timedelta(hours=2),
        ),
    ]

    with patch(
        "app.routers.spotify.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=tracks),
    ):
        resp = await client.get(
            f"/api/spotify/accounts/{account.id}/history?time_window=7",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "Song A"
    assert data[0]["artist"] == "Artist A"


@pytest.mark.asyncio
async def test_history_forbidden_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner2")
    other, other_token = await _make_user(db_session, fake_redis, sub="other2")
    account = await _make_spotify_account(db_session, owner)

    resp = await client.get(
        f"/api/spotify/accounts/{account.id}/history",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_history_triggers_token_refresh_when_expired(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    from app.services.music.base import Track

    user, token = await _make_user(db_session, fake_redis)
    # Create account with an already-expired token
    account = await _make_spotify_account(
        db_session,
        user,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )

    new_expires = datetime.now(UTC) + timedelta(hours=1)
    tracks: list[Track] = []

    with (
        patch(
            "app.routers.spotify.SpotifyAdapter.refresh_token",
            AsyncMock(return_value=("new-access", "new-refresh", new_expires)),
        ),
        patch(
            "app.routers.spotify.SpotifyAdapter.get_recently_played",
            AsyncMock(return_value=tracks),
        ),
    ):
        resp = await client.get(
            f"/api/spotify/accounts/{account.id}/history",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    # Verify the token was updated in the DB
    await db_session.refresh(account)
    assert crypto.decrypt(account.encrypted_access_token) == "new-access"
    assert crypto.decrypt(account.encrypted_refresh_token) == "new-refresh"


# ── 6. Crypto helpers ─────────────────────────────────────────────────────────


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "super-secret-token"
    ciphertext = crypto.encrypt(plaintext)
    assert ciphertext != plaintext
    assert crypto.decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_output_each_call() -> None:
    """Fernet uses random IVs so two encryptions of the same value differ."""
    token = "same-value"
    assert crypto.encrypt(token) != crypto.encrypt(token)
