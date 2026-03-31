"""Tests for Session 03 — Spotify Integration."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
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


@pytest.mark.asyncio
async def test_callback_second_account_creates_new_row(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Linking a second *different* Spotify account must create a new DB row."""
    user, _ = await _make_user(db_session, fake_redis)

    # First account already in the DB.
    await _make_spotify_account(db_session, user, spotify_user_id="spotify-first")

    # Second OAuth flow for a different Spotify user.
    state = "state-second-account"
    await fake_redis.set(f"spotify_state:{state}", str(user.id))

    token_response: dict[str, Any] = {
        "access_token": "sp-access-2",
        "refresh_token": "sp-refresh-2",
        "expires_in": 3600,
        "scope": "user-read-recently-played",
    }
    spotify_profile: dict[str, Any] = {
        "id": "spotify-second",
        "display_name": "Second Spotify User",
        "email": "second@spotify.com",
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
            f"/api/spotify/callback?code=authcode2&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)

    result = await db_session.execute(select(SpotifyAccount))
    accounts = result.scalars().all()
    assert len(accounts) == 2  # noqa: PLR2004
    spotify_ids = {a.spotify_user_id for a in accounts}
    assert spotify_ids == {"spotify-first", "spotify-second"}

    second = next(a for a in accounts if a.spotify_user_id == "spotify-second")
    assert second.user_id == user.id
    assert second.display_name == "Second Spotify User"
    assert second.email == "second@spotify.com"
    assert crypto.decrypt(second.encrypted_access_token) == "sp-access-2"
    assert crypto.decrypt(second.encrypted_refresh_token) == "sp-refresh-2"


@pytest.mark.asyncio
async def test_callback_relink_without_refresh_token_keeps_existing(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """When Spotify omits refresh_token on re-auth, the existing stored token is kept."""
    user, _ = await _make_user(db_session, fake_redis)
    account = await _make_spotify_account(db_session, user, spotify_user_id="spotify-relink")
    original_enc_refresh = account.encrypted_refresh_token

    state = "state-relink"
    await fake_redis.set(f"spotify_state:{state}", str(user.id))

    # Spotify response WITHOUT refresh_token (re-auth of already-approved app).
    token_response: dict[str, Any] = {
        "access_token": "new-access-token",
        # no "refresh_token" key
        "expires_in": 3600,
        "scope": "user-read-recently-played",
    }
    spotify_profile: dict[str, Any] = {
        "id": "spotify-relink",
        "display_name": "Relink User",
        "email": "relink@spotify.com",
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
            f"/api/spotify/callback?code=authcode-relink&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)

    await db_session.refresh(account)
    # Access token was updated.
    assert crypto.decrypt(account.encrypted_access_token) == "new-access-token"
    # Refresh token must be unchanged because Spotify did not return a new one.
    assert account.encrypted_refresh_token == original_enc_refresh


@pytest.mark.asyncio
async def test_callback_error_param_redirects_to_frontend(
    client: AsyncClient,
    fake_redis: FakeRedis,
) -> None:
    """When Spotify sends ?error=access_denied the callback must redirect gracefully."""
    state = "state-error"
    await fake_redis.set(f"spotify_state:{state}", "00000000-0000-0000-0000-000000000000")

    resp = await client.get(
        f"/api/spotify/callback?error=access_denied&state={state}",
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    assert "error=access_denied" in resp.headers["location"]
    # State must be consumed so it cannot be replayed.
    assert await fake_redis.get(f"spotify_state:{state}") is None


@pytest.mark.asyncio
async def test_callback_no_code_no_error_redirects_gracefully(
    client: AsyncClient,
    fake_redis: FakeRedis,
) -> None:
    """Callback with only a state (no code, no error) redirects with an unknown error."""
    state = "state-no-code"
    await fake_redis.set(f"spotify_state:{state}", "00000000-0000-0000-0000-000000000000")

    resp = await client.get(
        f"/api/spotify/callback?state={state}",
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    assert "error=" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_token_exchange_http_error_redirects(
    client: AsyncClient,
    fake_redis: FakeRedis,
) -> None:
    """An HTTP error from Spotify's token endpoint must redirect with an error, not crash."""
    state = "state-exchange-fail"
    await fake_redis.set(f"spotify_state:{state}", "00000000-0000-0000-0000-000000000000")

    mock_request = httpx.Request("POST", "https://accounts.spotify.com/api/token")
    mock_response = httpx.Response(400, request=mock_request)

    with patch(
        "app.routers.spotify.exchange_code",
        AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "bad request", request=mock_request, response=mock_response
            )
        ),
    ):
        resp = await client.get(
            f"/api/spotify/callback?code=badcode&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)
    assert "error=token_exchange_failed" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_token_exchange_network_error_redirects(
    client: AsyncClient,
    fake_redis: FakeRedis,
) -> None:
    """A network error during Spotify token exchange must redirect with an error, not crash."""
    state = "state-exchange-net-fail"
    await fake_redis.set(f"spotify_state:{state}", "00000000-0000-0000-0000-000000000000")

    mock_request = httpx.Request("POST", "https://accounts.spotify.com/api/token")

    with patch(
        "app.routers.spotify.exchange_code",
        AsyncMock(side_effect=httpx.ConnectTimeout("timed out", request=mock_request)),
    ):
        resp = await client.get(
            f"/api/spotify/callback?code=slowcode&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)
    assert "error=token_exchange_failed" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_profile_fetch_error_redirects(
    client: AsyncClient,
    fake_redis: FakeRedis,
) -> None:
    """An HTTP error when fetching the Spotify profile must redirect with an error, not crash."""
    state = "state-profile-fail"
    await fake_redis.set(f"spotify_state:{state}", "00000000-0000-0000-0000-000000000000")

    token_response: dict[str, Any] = {
        "access_token": "sp-access",
        "refresh_token": "sp-refresh",
        "expires_in": 3600,
        "scope": "user-read-recently-played",
    }
    mock_request = httpx.Request("GET", "https://api.spotify.com/v1/me")
    mock_response = httpx.Response(401, request=mock_request)

    with (
        patch(
            "app.routers.spotify.exchange_code",
            AsyncMock(return_value=token_response),
        ),
        patch(
            "app.routers.spotify.fetch_spotify_user",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "unauthorized", request=mock_request, response=mock_response
                )
            ),
        ),
    ):
        resp = await client.get(
            f"/api/spotify/callback?code=authcode&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)
    assert "error=profile_fetch_failed" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_no_refresh_token_for_new_account_redirects(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """When Spotify omits refresh_token for a brand-new (or previously unlinked) account,
    the callback must redirect to the frontend with error=no_refresh_token instead of
    raising an HTTPException or crashing.
    """
    user, _ = await _make_user(db_session, fake_redis)
    state = "state-no-refresh-new"
    await fake_redis.set(f"spotify_state:{state}", str(user.id))

    # Spotify response WITHOUT refresh_token for an account not in the DB.
    token_response: dict[str, Any] = {
        "access_token": "new-access-token",
        # no "refresh_token" key
        "expires_in": 3600,
        "scope": "user-read-recently-played",
    }
    spotify_profile: dict[str, Any] = {
        "id": "spotify-never-seen",
        "display_name": "New User",
        "email": "new@spotify.com",
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
            f"/api/spotify/callback?code=authcode-no-refresh&state={state}",
            follow_redirects=False,
        )

    assert resp.status_code in (302, 307)
    assert "error=no_refresh_token" in resp.headers["location"]
    # No account should have been created.
    result = await db_session.execute(
        select(SpotifyAccount).where(SpotifyAccount.spotify_user_id == "spotify-never-seen")
    )
    assert result.scalar_one_or_none() is None


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
