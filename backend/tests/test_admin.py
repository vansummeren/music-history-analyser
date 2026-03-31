"""Tests for admin endpoints."""
from __future__ import annotations

import uuid
from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.services import auth_service, crypto
from app.services.ai.base import AnalysisResult
from app.services.music.base import Track
from tests.conftest import FakeRedis

from datetime import UTC, datetime, timedelta


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_admin(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "admin-sub",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="admin@example.com", display_name="Admin"
    )
    user.role = "admin"
    await db.commit()
    await db.refresh(user)
    token = auth_service.create_access_token(user.id)
    return user, token


async def _make_plain_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "plain-sub",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="user@example.com", display_name="User"
    )
    token = auth_service.create_access_token(user.id)
    return user, token


async def _make_spotify_account(db: AsyncSession, user: User) -> SpotifyAccount:
    account = SpotifyAccount(
        user_id=user.id,
        spotify_user_id="spotify-test-id",
        display_name="Test Spotify",
        email="spotify@example.com",
        encrypted_access_token=crypto.encrypt("access-token"),
        encrypted_refresh_token=crypto.encrypt("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes="user-read-recently-played",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _make_ai_config(db: AsyncSession, user: User) -> AIConfig:
    config = AIConfig(
        user_id=user.id,
        provider="claude",
        display_name="Test Claude",
        encrypted_api_key=crypto.encrypt("sk-test"),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


def _smtp_ctx(sent: list[MIMEMultipart]) -> MagicMock:
    smtp_instance = AsyncMock()
    async def _send(msg: MIMEMultipart) -> None:
        sent.append(msg)
    smtp_instance.send_message = _send
    smtp_instance.login = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=smtp_instance)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ── POST /api/admin/test-email ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_test_email_sends_email(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin can send a test email."""
    _, token = await _make_admin(db_session, fake_redis)
    sent: list[MIMEMultipart] = []
    with patch("app.services.email_service.aiosmtplib.SMTP", return_value=_smtp_ctx(sent)):
        resp = await client.post(
            "/api/admin/test-email",
            json={"recipient": "test@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recipient"] == "test@example.com"
    assert len(sent) == 1
    assert sent[0]["To"] == "test@example.com"


@pytest.mark.asyncio
async def test_admin_test_email_blocked_for_plain_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Non-admin users cannot use the test-email endpoint."""
    _, token = await _make_plain_user(db_session, fake_redis)
    resp = await client.post(
        "/api/admin/test-email",
        json={"recipient": "test@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_test_email_requires_auth(
    client: AsyncClient,
) -> None:
    """Unauthenticated requests are rejected with 401."""
    resp = await client.post("/api/admin/test-email", json={"recipient": "t@example.com"})
    assert resp.status_code == 401


# ── POST /api/admin/test-spotify/{account_id} ────────────────────────────────


@pytest.mark.asyncio
async def test_admin_test_spotify_returns_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin can fetch recent Spotify tracks for their account."""
    admin, token = await _make_admin(db_session, fake_redis)
    account = await _make_spotify_account(db_session, admin)

    fake_tracks = [
        Track(title="Song A", artist="Artist A", album="Album A", played_at=datetime.now(UTC)),
        Track(title="Song B", artist="Artist B", album="Album B", played_at=datetime.now(UTC)),
    ]
    with patch(
        "app.routers.admin.SpotifyAdapter.get_recently_played",
        AsyncMock(return_value=fake_tracks),
    ):
        resp = await client.post(
            f"/api/admin/test-spotify/{account.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["account_id"] == str(account.id)
    assert data["tracks"][0]["title"] == "Song A"


@pytest.mark.asyncio
async def test_admin_test_spotify_404_for_unknown_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Returns 404 when the Spotify account does not exist."""
    _, token = await _make_admin(db_session, fake_redis)
    resp = await client.post(
        f"/api/admin/test-spotify/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_test_spotify_403_for_other_users_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin cannot test a Spotify account that belongs to another user."""
    admin, admin_token = await _make_admin(db_session, fake_redis)
    other_user, _ = await _make_plain_user(db_session, fake_redis)
    account = await _make_spotify_account(db_session, other_user)

    resp = await client.post(
        f"/api/admin/test-spotify/{account.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_test_spotify_blocked_for_plain_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Non-admin users cannot use the test-spotify endpoint."""
    _, plain_token = await _make_plain_user(db_session, fake_redis)
    resp = await client.post(
        f"/api/admin/test-spotify/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 403


# ── POST /api/admin/test-ai/{config_id} ──────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_test_ai_returns_result(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin can send a test prompt to their configured AI provider."""
    admin, token = await _make_admin(db_session, fake_redis)
    config = await _make_ai_config(db_session, admin)

    fake_result = AnalysisResult(
        text="Hello! I am working correctly.",
        model="claude-3-5-haiku-20241022",
        input_tokens=20,
        output_tokens=10,
    )
    with patch(
        "app.routers.admin.ClaudeAdapter.analyse",
        AsyncMock(return_value=fake_result),
    ):
        resp = await client.post(
            f"/api/admin/test-ai/{config.id}",
            json={"prompt": "Are you working?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Hello! I am working correctly."
    assert data["provider"] == "claude"
    assert data["input_tokens"] == 20
    assert data["config_id"] == str(config.id)


@pytest.mark.asyncio
async def test_admin_test_ai_404_for_unknown_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Returns 404 when the AI config does not exist."""
    _, token = await _make_admin(db_session, fake_redis)
    resp = await client.post(
        f"/api/admin/test-ai/{uuid.uuid4()}",
        json={"prompt": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_test_ai_403_for_other_users_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin cannot test an AI config that belongs to another user."""
    admin, admin_token = await _make_admin(db_session, fake_redis)
    other_user, _ = await _make_plain_user(db_session, fake_redis)
    config = await _make_ai_config(db_session, other_user)

    resp = await client.post(
        f"/api/admin/test-ai/{config.id}",
        json={"prompt": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_test_ai_blocked_for_plain_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Non-admin users cannot use the test-ai endpoint."""
    _, plain_token = await _make_plain_user(db_session, fake_redis)
    resp = await client.post(
        f"/api/admin/test-ai/{uuid.uuid4()}",
        json={"prompt": "test"},
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 403
