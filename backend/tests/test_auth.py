"""Auth acceptance tests for Session 02."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import config as app_config
from app.main import _sanitize
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


def test_resolve_role_uses_configured_group_name() -> None:
    original = app_config.settings.admin_group_name
    app_config.settings.admin_group_name = "Administrators"
    try:
        assert auth_service.resolve_role(["administrators"]) == "admin"
        assert auth_service.resolve_role(["admin"]) == "user"
    finally:
        app_config.settings.admin_group_name = original


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


# ── 11. OIDC redirect_uri — explicit override ─────────────────────────────────


@pytest.mark.asyncio
async def test_oidc_login_uses_configured_redirect_uri(
    client: AsyncClient,
    fake_redis: FakeRedis,
    mock_oidc_discovery: dict[str, Any],
) -> None:
    """When OIDC_REDIRECT_URI is set it must appear in the IdP authorization URL."""
    original_uri = app_config.settings.oidc_redirect_uri
    original_disc = app_config.settings.oidc_discovery_url
    app_config.settings.oidc_redirect_uri = "https://prod.example.com/api/auth/oidc/callback"
    app_config.settings.oidc_discovery_url = "https://idp.example.com/.well-known/openid-configuration"
    try:
        response = await client.get("/api/auth/oidc/login", follow_redirects=False)
    finally:
        app_config.settings.oidc_redirect_uri = original_uri
        app_config.settings.oidc_discovery_url = original_disc

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "https%3A%2F%2Fprod.example.com%2Fapi%2Fauth%2Foidc%2Fcallback" in location


@pytest.mark.asyncio
async def test_oidc_login_scope_uses_percent_encoding(
    client: AsyncClient,
    fake_redis: FakeRedis,
    mock_oidc_discovery: dict[str, Any],
) -> None:
    """The scope parameter must be percent-encoded (spaces as %20, not +)."""
    original_disc = app_config.settings.oidc_discovery_url
    app_config.settings.oidc_discovery_url = "https://idp.example.com/.well-known/openid-configuration"
    try:
        response = await client.get("/api/auth/oidc/login", follow_redirects=False)
    finally:
        app_config.settings.oidc_discovery_url = original_disc

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "openid%20email%20profile" in location
    assert "openid+email+profile" not in location


# ── 13. OIDC discovery errors surface as 502 ──────────────────────────────────


@pytest.mark.asyncio
async def test_oidc_login_discovery_error_returns_502(
    client: AsyncClient,
    fake_redis: FakeRedis,
) -> None:
    """When fetch_oidc_discovery raises HTTPException(502), the login endpoint
    must pass that status code through to the caller.
    """
    original_disc = app_config.settings.oidc_discovery_url
    app_config.settings.oidc_discovery_url = "https://idp.example.com/.well-known/openid-configuration"
    try:
        with patch(
            "app.services.auth_service.fetch_oidc_discovery",
            AsyncMock(side_effect=HTTPException(status_code=502, detail="IdP unreachable")),
        ):
            response = await client.get("/api/auth/oidc/login", follow_redirects=False)
    finally:
        app_config.settings.oidc_discovery_url = original_disc

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_fetch_oidc_discovery_http_status_error_raises_502() -> None:
    """fetch_oidc_discovery must raise HTTPException(502) when the IdP
    returns a non-2xx HTTP status.
    """
    discovery_url = "https://idp.example.com/.well-known/test-config"
    auth_service.clear_oidc_discovery_cache()

    mock_request = httpx.Request("GET", discovery_url)
    mock_response = httpx.Response(503, request=mock_request)

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=mock_request, response=mock_response
    )
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = False

    with (
        patch("app.services.auth_service.httpx.AsyncClient", return_value=mock_cm),
        pytest.raises(HTTPException) as exc_info,
    ):
        await auth_service.fetch_oidc_discovery(discovery_url)

    assert exc_info.value.status_code == 502
    assert "503" in exc_info.value.detail


@pytest.mark.asyncio
async def test_fetch_oidc_discovery_network_error_raises_502() -> None:
    """fetch_oidc_discovery must raise HTTPException(502) on network errors
    (e.g. DNS failure, connection refused, timeout).
    """
    discovery_url = "https://idp.example.com/.well-known/test-network"
    auth_service.clear_oidc_discovery_cache()

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = False

    with (
        patch("app.services.auth_service.httpx.AsyncClient", return_value=mock_cm),
        pytest.raises(HTTPException) as exc_info,
    ):
        await auth_service.fetch_oidc_discovery(discovery_url)

    assert exc_info.value.status_code == 502


# ── 14. _sanitize helper strips control characters ────────────────────────────


def test_sanitize_strips_carriage_return() -> None:
    """_sanitize must remove \\r so CRLF env-var values don't corrupt the banner."""
    assert _sanitize("https://example.com/\r") == "https://example.com/"


def test_sanitize_collapses_embedded_newline() -> None:
    """_sanitize must collapse \\n so multiline values stay on one banner line."""
    assert _sanitize("line1\nline2") == "line1 line2"


def test_sanitize_leaves_normal_strings_unchanged() -> None:
    assert _sanitize("https://example.com/api") == "https://example.com/api"



@pytest.mark.asyncio
async def test_saml_acs_uses_meta_refresh(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """SAML ACS must redirect via <meta http-equiv="refresh">, not an inline script.

    An inline <script> is blocked by the Content-Security-Policy (script-src 'self').
    """
    from unittest.mock import MagicMock, patch

    mock_auth = MagicMock()
    mock_auth.process_response.return_value = None
    mock_auth.get_errors.return_value = []
    mock_auth.get_attributes.return_value = {
        "email": ["saml-user@example.com"],
        "displayName": ["SAML User"],
    }
    mock_auth.get_nameid.return_value = "saml-nameid-123"

    with patch("app.routers.auth._build_saml_auth", return_value=mock_auth):
        response = await client.post("/api/auth/saml/acs", data={})

    assert response.status_code == 200
    body = response.text

    # Must use meta-refresh, NOT an inline script
    assert '<meta http-equiv="refresh"' in body
    assert "<script>" not in body

    # The callback URL must be present in the meta-refresh tag
    assert "access_token=" in body
    assert "refresh_token=" in body
