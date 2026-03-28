"""Auth acceptance tests for Session 02."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import config as app_config
from app.models.user import User
from app.services import auth_service
from tests.conftest import FakeRedis

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "test-sub",
    provider: str = "oidc",
    email: str | None = "test@example.com",
    display_name: str | None = "Test User",
    role: str = "user",
) -> tuple[User, str, str]:
    """Create a user in the DB and issue valid tokens."""
    user = await auth_service.upsert_user(
        db,
        sub=sub,
        provider=provider,
        email=email,
        display_name=display_name,
        role=role,
    )
    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, redis)
    return user, access_token, refresh_token


# ── 1. Unauthenticated requests return 401 ────────────────────────────────────


@pytest.mark.asyncio
async def test_users_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


# ── 2. Valid token — /api/auth/me returns user profile ───────────────────────


@pytest.mark.asyncio
async def test_auth_me_returns_profile(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, access_token, _ = await _make_user(db_session, fake_redis)

    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "test-sub"
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"


# ── 3. First OIDC login creates a new user row ────────────────────────────────


@pytest.mark.asyncio
async def test_oidc_callback_creates_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
    mock_oidc_discovery: dict[str, Any],
) -> None:
    # Store a valid OIDC state/nonce in fake Redis
    state = "teststate123"
    nonce = "testnonce456"
    await auth_service.store_oidc_state(state, nonce, fake_redis)

    userinfo: dict[str, Any] = {
        "sub": "oidc-new-user",
        "email": "new@example.com",
        "name": "New User",
        "roles": [],
    }

    with (
        patch(
            "app.routers.auth.auth_service.exchange_oidc_code",
            AsyncMock(return_value={"access_token": "idp-access-token"}),
        ),
        patch(
            "app.routers.auth.auth_service.fetch_oidc_userinfo",
            AsyncMock(return_value=userinfo),
        ),
    ):
        response = await client.get(
            f"/api/auth/oidc/callback?code=authcode&state={state}",
            follow_redirects=False,
        )

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "access_token=" in location

    # Verify a user row was created
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.sub == "oidc-new-user"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.email == "new@example.com"
    assert user.role == "user"


# ── 4. Re-login with the same identity does NOT create a duplicate ────────────


@pytest.mark.asyncio
async def test_oidc_callback_no_duplicate_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
    mock_oidc_discovery: dict[str, Any],
) -> None:
    from sqlalchemy import func, select

    # First login
    await auth_service.upsert_user(
        db_session,
        sub="oidc-existing",
        provider="oidc",
        email="old@example.com",
        display_name="Old Name",
        role="user",
    )

    state = "state-dup"
    await auth_service.store_oidc_state(state, "nonce-dup", fake_redis)

    userinfo: dict[str, Any] = {
        "sub": "oidc-existing",
        "email": "updated@example.com",
        "name": "Updated Name",
        "roles": [],
    }

    with (
        patch(
            "app.routers.auth.auth_service.exchange_oidc_code",
            AsyncMock(return_value={"access_token": "idp-token"}),
        ),
        patch(
            "app.routers.auth.auth_service.fetch_oidc_userinfo",
            AsyncMock(return_value=userinfo),
        ),
    ):
        await client.get(
            f"/api/auth/oidc/callback?code=code2&state={state}",
            follow_redirects=False,
        )

    # Still only one row
    count_result = await db_session.execute(
        select(func.count()).select_from(User).where(User.sub == "oidc-existing")
    )
    assert count_result.scalar() == 1

    # Email was updated
    result = await db_session.execute(
        select(User).where(User.sub == "oidc-existing")
    )
    user = result.scalar_one()
    assert user.email == "updated@example.com"


# ── 5. Role is synced from the IdP on every login ─────────────────────────────


@pytest.mark.asyncio
async def test_oidc_callback_syncs_role_to_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
    mock_oidc_discovery: dict[str, Any],
) -> None:
    from sqlalchemy import select

    state = "state-role"
    await auth_service.store_oidc_state(state, "nonce-role", fake_redis)

    userinfo: dict[str, Any] = {
        "sub": "oidc-promoted",
        "email": "admin@example.com",
        "name": "Admin User",
        "roles": ["admin"],
    }

    with (
        patch(
            "app.routers.auth.auth_service.exchange_oidc_code",
            AsyncMock(return_value={"access_token": "idp-token"}),
        ),
        patch(
            "app.routers.auth.auth_service.fetch_oidc_userinfo",
            AsyncMock(return_value=userinfo),
        ),
    ):
        await client.get(
            f"/api/auth/oidc/callback?code=code3&state={state}",
            follow_redirects=False,
        )

    result = await db_session.execute(
        select(User).where(User.sub == "oidc-promoted")
    )
    user = result.scalar_one()
    assert user.role == "admin"


# ── 6. Logout invalidates the token ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_invalidates_token(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, access_token, refresh_token = await _make_user(db_session, fake_redis)

    # Confirm the token works before logout
    resp_before = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp_before.status_code == 200

    # Logout
    resp_logout = await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp_logout.status_code == 200

    # Token must now be rejected
    resp_after = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp_after.status_code == 401


# ── 7. require_role dependency ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_role_admin_blocks_plain_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """A route guarded by require_role("admin") must reject a plain user."""
    from fastapi import HTTPException

    from app.dependencies import require_role

    _, access_token, _ = await _make_user(db_session, fake_redis, role="user")

    # Call the dependency directly to verify it raises 403 for a plain user.
    # We build a fake request with the token stored in fake_redis overrides.
    from unittest.mock import MagicMock

    mock_user = MagicMock(spec=User)
    mock_user.role = "user"

    check = require_role("admin")
    with pytest.raises(HTTPException) as exc_info:
        await check(user=mock_user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_admin_allows_admin_user(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """require_role("admin") must pass through an admin user unchanged."""
    from unittest.mock import MagicMock

    from app.dependencies import require_role

    mock_user = MagicMock(spec=User)
    mock_user.role = "admin"

    check = require_role("admin")
    result = await check(user=mock_user)
    assert result is mock_user


# ── 8. Invalid / tampered tokens ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tampered_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert response.status_code == 401


# ── 9. resolve_role helper ────────────────────────────────────────────────────


def test_resolve_role_returns_admin_for_admin_claim() -> None:
    assert auth_service.resolve_role(["admin", "user"]) == "admin"


def test_resolve_role_is_case_insensitive() -> None:
    assert auth_service.resolve_role(["Admin"]) == "admin"


def test_resolve_role_defaults_to_user() -> None:
    assert auth_service.resolve_role([]) == "user"
    assert auth_service.resolve_role(["viewer"]) == "user"


# ── 10. /api/auth/login dispatcher ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_dispatch_oidc(client: AsyncClient) -> None:
    """GET /api/auth/login redirects to the OIDC endpoint when auth_provider=oidc."""
    original = app_config.settings.auth_provider
    app_config.settings.auth_provider = "oidc"
    try:
        response = await client.get("/api/auth/login", follow_redirects=False)
    finally:
        app_config.settings.auth_provider = original

    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/api/auth/oidc/login")


@pytest.mark.asyncio
async def test_login_dispatch_saml(client: AsyncClient) -> None:
    """GET /api/auth/login redirects to the SAML endpoint when auth_provider=saml."""
    original = app_config.settings.auth_provider
    app_config.settings.auth_provider = "saml"
    try:
        response = await client.get("/api/auth/login", follow_redirects=False)
    finally:
        app_config.settings.auth_provider = original

    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/api/auth/saml/login")
