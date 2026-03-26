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

    class OverLimitFakeRedis:
        """Always returns a count above the limit so 429 is triggered."""

        async def incr(self, key: str) -> int:
            return 21  # limit is 20

        async def expire(self, key: str, seconds: int) -> None:
            pass

    async def _override_redis() -> Any:
        return OverLimitFakeRedis()

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

    class OverLimitFakeRedis:
        async def incr(self, key: str) -> int:
            return 100  # way over the limit

        async def expire(self, key: str, seconds: int) -> None:
            pass

    async def _override_redis() -> Any:
        return OverLimitFakeRedis()

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
