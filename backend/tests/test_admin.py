"""Tests for diagnostic (admin) endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
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

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "test-sub",
    email: str = "user@example.com",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email=email, display_name="Test User"
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
async def test_test_email_sends_email(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Any authenticated user can send a test email."""
    _, token = await _make_user(db_session, fake_redis)
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
async def test_test_email_requires_auth(
    client: AsyncClient,
) -> None:
    """Unauthenticated requests are rejected with 401."""
    resp = await client.post("/api/admin/test-email", json={"recipient": "t@example.com"})
    assert resp.status_code == 401


# ── POST /api/admin/test-spotify/{account_id} ────────────────────────────────


@pytest.mark.asyncio
async def test_test_spotify_returns_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Authenticated user can fetch recent Spotify tracks for their account."""
    user, token = await _make_user(db_session, fake_redis)
    account = await _make_spotify_account(db_session, user)

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
async def test_test_spotify_404_for_unknown_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Returns 404 when the Spotify account does not exist."""
    _, token = await _make_user(db_session, fake_redis)
    resp = await client.post(
        f"/api/admin/test-spotify/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_test_spotify_403_for_other_users_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """User cannot test a Spotify account that belongs to another user."""
    user, token = await _make_user(
        db_session, fake_redis, sub="user-a", email="a@example.com"
    )
    other_user, _ = await _make_user(
        db_session, fake_redis, sub="user-b", email="b@example.com"
    )
    account = await _make_spotify_account(db_session, other_user)

    resp = await client.post(
        f"/api/admin/test-spotify/{account.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_test_spotify_requires_auth(
    client: AsyncClient,
) -> None:
    """Unauthenticated requests are rejected with 401."""
    resp = await client.post(f"/api/admin/test-spotify/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── POST /api/admin/test-ai/{config_id} ──────────────────────────────────────


@pytest.mark.asyncio
async def test_test_ai_returns_result(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Authenticated user can send a test prompt to their AI provider."""
    user, token = await _make_user(db_session, fake_redis)
    config = await _make_ai_config(db_session, user)

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
async def test_test_ai_404_for_unknown_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Returns 404 when the AI config does not exist."""
    _, token = await _make_user(db_session, fake_redis)
    resp = await client.post(
        f"/api/admin/test-ai/{uuid.uuid4()}",
        json={"prompt": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_test_ai_403_for_other_users_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """User cannot test an AI config that belongs to another user."""
    user, token = await _make_user(
        db_session, fake_redis, sub="user-a", email="a@example.com"
    )
    other_user, _ = await _make_user(
        db_session, fake_redis, sub="user-b", email="b@example.com"
    )
    config = await _make_ai_config(db_session, other_user)

    resp = await client.post(
        f"/api/admin/test-ai/{config.id}",
        json={"prompt": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_test_ai_requires_auth(
    client: AsyncClient,
) -> None:
    """Unauthenticated requests are rejected with 401."""
    resp = await client.post(
        f"/api/admin/test-ai/{uuid.uuid4()}",
        json={"prompt": "test"},
    )
    assert resp.status_code == 401


# ── GET /api/admin/tables ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tables_requires_admin_role(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Regular users receive 403 when accessing the tables endpoint."""
    _, token = await _make_user(db_session, fake_redis)
    resp = await client.get(
        "/api/admin/tables",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tables_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated requests to /tables are rejected with 401."""
    resp = await client.get("/api/admin/tables")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tables_returns_row_counts_for_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin users receive a list of table row counts."""
    user, token = await _make_user(db_session, fake_redis)
    user.role = "admin"
    await db_session.commit()

    resp = await client.get(
        "/api/admin/tables",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "tables" in data
    table_names = [row["table"] for row in data["tables"]]
    assert "users" in table_names
    assert "spotify_accounts" in table_names
    for row in data["tables"]:
        assert "row_count" in row
        assert isinstance(row["row_count"], int)


# ── GET /api/admin/users ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Regular users receive 403 when accessing the user list."""
    _, token = await _make_user(db_session, fake_redis, sub="reg-user-list")
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated requests to /users are rejected with 401."""
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_users_returns_all_users(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin users receive a list of all users with summary counts."""
    admin, admin_token = await _make_user(db_session, fake_redis, sub="admin-list-sub")
    admin.role = "admin"
    await db_session.commit()

    # Create a second user
    await _make_user(db_session, fake_redis, sub="other-list-sub", email="other@example.com")

    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    user_ids = [u["id"] for u in data]
    assert str(admin.id) in user_ids

    for entry in data:
        assert "spotify_accounts_count" in entry
        assert "analyses_count" in entry
        assert "play_events_count" in entry


# ── GET /api/admin/users/{user_id} ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_detail_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Regular users receive 403 when accessing user detail."""
    user, token = await _make_user(db_session, fake_redis, sub="reg-detail-sub")
    resp = await client.get(
        f"/api/admin/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_user_detail_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Returns 404 for an unknown user ID."""
    admin, admin_token = await _make_user(db_session, fake_redis, sub="admin-detail-404")
    admin.role = "admin"
    await db_session.commit()

    resp = await client.get(
        f"/api/admin/users/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_detail_returns_data(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Admin receives full user detail including Spotify accounts and analyses."""
    admin, admin_token = await _make_user(db_session, fake_redis, sub="admin-detail-ok")
    admin.role = "admin"
    await db_session.commit()

    target_user, _ = await _make_user(
        db_session, fake_redis, sub="detail-target", email="target@example.com"
    )
    account = await _make_spotify_account(db_session, target_user)

    resp = await client.get(
        f"/api/admin/users/{target_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(target_user.id)
    assert data["email"] == "target@example.com"
    assert "spotify_accounts" in data
    assert "analyses" in data
    assert "schedules" in data
    assert len(data["spotify_accounts"]) == 1
    assert data["spotify_accounts"][0]["id"] == str(account.id)
    assert "play_events_count" in data["spotify_accounts"][0]


# ── Application logs ──────────────────────────────────────────────────────────


async def _seed_logs(db: AsyncSession) -> None:
    """Insert a small set of log records with known level/service values."""
    from app.models.app_log import AppLog

    entries = [
        AppLog(id=uuid.uuid4(), created_at=datetime.now(UTC), level="INFO", service="backend", logger_name="app.test", message="Info backend"),
        AppLog(id=uuid.uuid4(), created_at=datetime.now(UTC), level="INFO", service="worker", logger_name="app.test", message="Info worker"),
        AppLog(id=uuid.uuid4(), created_at=datetime.now(UTC), level="ERROR", service="backend", logger_name="app.test", message="Error backend"),
        AppLog(id=uuid.uuid4(), created_at=datetime.now(UTC), level="WARNING", service="beat", logger_name="app.test", message="Warning beat"),
    ]
    for entry in entries:
        db.add(entry)
    await db.commit()


@pytest.mark.asyncio
async def test_get_log_services_returns_distinct_names(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    admin, admin_token = await _make_user(
        db_session, fake_redis, sub="svc-admin", email="svcadmin@example.com"
    )
    admin.role = "admin"
    await db_session.commit()
    await _seed_logs(db_session)

    resp = await client.get(
        "/api/admin/logs/services",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["services"]) == {"backend", "beat", "worker"}


@pytest.mark.asyncio
async def test_get_logs_filter_by_level(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    admin, admin_token = await _make_user(
        db_session, fake_redis, sub="lvl-admin", email="lvladmin@example.com"
    )
    admin.role = "admin"
    await db_session.commit()
    await _seed_logs(db_session)

    resp = await client.get(
        "/api/admin/logs?level=INFO",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(item["level"] == "INFO" for item in data["items"])


@pytest.mark.asyncio
async def test_get_logs_filter_by_single_service(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    admin, admin_token = await _make_user(
        db_session, fake_redis, sub="svc1-admin", email="svc1admin@example.com"
    )
    admin.role = "admin"
    await db_session.commit()
    await _seed_logs(db_session)

    resp = await client.get(
        "/api/admin/logs?service=backend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(item["service"] == "backend" for item in data["items"])


@pytest.mark.asyncio
async def test_get_logs_filter_by_multiple_services(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    admin, admin_token = await _make_user(
        db_session, fake_redis, sub="svc2-admin", email="svc2admin@example.com"
    )
    admin.role = "admin"
    await db_session.commit()
    await _seed_logs(db_session)

    resp = await client.get(
        "/api/admin/logs?service=backend&service=worker",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert all(item["service"] in {"backend", "worker"} for item in data["items"])


@pytest.mark.asyncio
async def test_get_logs_filter_by_search(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    admin, admin_token = await _make_user(
        db_session, fake_redis, sub="srch-admin", email="srchadmin@example.com"
    )
    admin.role = "admin"
    await db_session.commit()
    await _seed_logs(db_session)

    resp = await client.get(
        "/api/admin/logs?search=Error",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["level"] == "ERROR"


@pytest.mark.asyncio
async def test_get_log_services_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(
        db_session, fake_redis, sub="nonadmin-svc", email="nonadminsvc@example.com"
    )
    resp = await client.get(
        "/api/admin/logs/services",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
