"""Tests for security headers middleware and rate limiting."""
from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.redis_client import get_redis

# ── Security headers ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_headers_present() -> None:
    """Every response must carry the OWASP security headers."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert "strict-transport-security" in response.headers
    assert "x-frame-options" in response.headers
    assert "x-content-type-options" in response.headers
    assert "referrer-policy" in response.headers
    assert "content-security-policy" in response.headers
    assert "permissions-policy" in response.headers


@pytest.mark.asyncio
async def test_x_frame_options_is_deny() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_x_content_type_nosniff() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_hsts_header() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    hsts = response.headers["strict-transport-security"]
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


# ── Rate limiting ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_allows_requests_under_limit(
    client: AsyncClient,
) -> None:
    """Requests under the limit must go through (may get 503 if OIDC not configured)."""
    response = await client.get("/api/auth/oidc/login")
    # 503 = OIDC not configured in test env; what matters is NOT 429
    assert response.status_code != 429


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_limit_exceeded() -> None:
    """Exceeding the rate limit must return HTTP 429."""

    class CountingFakeRedis:
        def __init__(self) -> None:
            self._store: dict[str, str] = {}

        async def get(self, key: str) -> str | None:
            return self._store.get(key)

        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            self._store[key] = value

        async def delete(self, key: str) -> None:
            self._store.pop(key, None)

    fake_redis = CountingFakeRedis()
    # Pre-fill the counter to the limit (20) so the next request is the 21st.
    # httpx ASGITransport sets the client address to 127.0.0.1.
    fake_redis._store["rl:login:/api/auth/oidc/login:127.0.0.1"] = "20"

    async def _override_redis() -> Any:
        return fake_redis

    app.dependency_overrides[get_redis] = _override_redis
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/auth/oidc/login")
        assert response.status_code == 429
        assert "Too many requests" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_rate_limit_retry_after_header() -> None:
    """HTTP 429 response must include a Retry-After header."""

    class FullFakeRedis:
        async def get(self, key: str) -> str | None:
            return "100"  # way over the limit

        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            pass

        async def delete(self, key: str) -> None:
            pass

    async def _override_redis() -> Any:
        return FullFakeRedis()

    app.dependency_overrides[get_redis] = _override_redis
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/auth/oidc/login")
        assert response.status_code == 429
        assert "retry-after" in response.headers
    finally:
        app.dependency_overrides.pop(get_redis, None)
