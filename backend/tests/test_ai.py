"""Tests for Session 04 — AI Config endpoints."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.models.user import User
from app.services import auth_service, crypto
from tests.conftest import FakeRedis

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "ai-test-sub",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="user@example.com", display_name="Test User"
    )
    token = auth_service.create_access_token(user.id)
    return user, token


async def _make_ai_config(
    db: AsyncSession,
    user: User,
    *,
    provider: str = "claude",
    display_name: str = "My Claude",
    api_key: str = "sk-test-key",
) -> AIConfig:
    config = AIConfig(
        user_id=user.id,
        provider=provider,
        display_name=display_name,
        encrypted_api_key=crypto.encrypt(api_key),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


# ── 1. POST /api/ai-configs ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_ai_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis)

    resp = await client.post(
        "/api/ai-configs",
        json={"provider": "claude", "display_name": "My Claude", "api_key": "sk-abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "claude"
    assert data["display_name"] == "My Claude"
    assert "api_key" not in data  # key must not be returned


@pytest.mark.asyncio
async def test_create_ai_config_perplexity(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis, sub="sub-perplexity")

    resp = await client.post(
        "/api/ai-configs",
        json={"provider": "perplexity", "display_name": "My Perplexity", "api_key": "pplx-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["provider"] == "perplexity"


@pytest.mark.asyncio
async def test_create_ai_config_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/ai-configs",
        json={"provider": "claude", "display_name": "x", "api_key": "y"},
    )
    assert resp.status_code == 401


# ── 2. GET /api/ai-configs ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ai_configs(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-list")
    await _make_ai_config(db_session, user, display_name="Config 1")
    await _make_ai_config(db_session, user, display_name="Config 2")

    resp = await client.get("/api/ai-configs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_ai_configs_isolated_per_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user_a, token_a = await _make_user(db_session, fake_redis, sub="sub-a")
    user_b, token_b = await _make_user(db_session, fake_redis, sub="sub-b")
    await _make_ai_config(db_session, user_a)

    resp = await client.get("/api/ai-configs", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert resp.json() == []


# ── 3. DELETE /api/ai-configs/{id} ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_ai_config(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-del")
    config = await _make_ai_config(db_session, user)

    resp = await client.delete(
        f"/api/ai-configs/{config.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    deleted = await db_session.get(AIConfig, config.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_delete_ai_config_forbidden_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-ai")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-ai")
    config = await _make_ai_config(db_session, owner)

    resp = await client.delete(
        f"/api/ai-configs/{config.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_ai_config_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis, sub="sub-404ai")
    resp = await client.delete(
        f"/api/ai-configs/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── 4. API key is stored encrypted ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_key_stored_encrypted(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-enc")
    resp = await client.post(
        "/api/ai-configs",
        json={"provider": "claude", "display_name": "Enc Test", "api_key": "secret-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    config_id = uuid.UUID(resp.json()["id"])

    from sqlalchemy import select

    from app.models.ai_config import AIConfig as AIConfigModel

    result = await db_session.execute(
        select(AIConfigModel).where(AIConfigModel.id == config_id)
    )
    config = result.scalar_one()
    assert config.encrypted_api_key != "secret-key"
    assert crypto.decrypt(config.encrypted_api_key) == "secret-key"
