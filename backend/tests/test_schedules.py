"""Tests for Session 05 — Schedule endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.models.analysis import Analysis
from app.models.schedule import Schedule
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.services import auth_service, crypto
from tests.conftest import FakeRedis

# ── Helpers ───────────────────────────────────────────────────────────────────

_CRON = "0 8 * * 1"  # every Monday at 08:00


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "sched-test-sub",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="user@example.com", display_name="Test User"
    )
    token = auth_service.create_access_token(user.id)
    return user, token


async def _make_analysis(db: AsyncSession, user: User) -> Analysis:
    spotify = SpotifyAccount(
        user_id=user.id,
        spotify_user_id="spotify-uid",
        encrypted_access_token=crypto.encrypt("access"),
        encrypted_refresh_token=crypto.encrypt("refresh"),
        token_expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    db.add(spotify)

    ai_config = AIConfig(
        user_id=user.id,
        provider="claude",
        display_name="Test Claude",
        encrypted_api_key=crypto.encrypt("sk-test"),
    )
    db.add(ai_config)
    await db.flush()

    analysis = Analysis(
        user_id=user.id,
        spotify_account_id=spotify.id,
        ai_config_id=ai_config.id,
        name="Test Analysis",
        prompt="Describe my taste.",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


# ── 1. POST /api/schedules ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_schedule(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis)
    analysis = await _make_analysis(db_session, user)

    resp = await client.post(
        "/api/schedules",
        json={
            "analysis_id": str(analysis.id),
            "cron": _CRON,
            "time_window_days": 7,
            "recipient_email": "test@example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["cron"] == _CRON
    assert data["time_window_days"] == 7
    assert data["recipient_email"] == "test@example.com"
    assert data["is_active"] is True
    assert "next_run_at" in data


@pytest.mark.asyncio
async def test_create_schedule_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/schedules",
        json={
            "analysis_id": str(uuid.uuid4()),
            "cron": _CRON,
            "recipient_email": "x@y.com",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_schedule_invalid_cron(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-bad-cron")
    analysis = await _make_analysis(db_session, user)

    resp = await client.post(
        "/api/schedules",
        json={
            "analysis_id": str(analysis.id),
            "cron": "not-a-cron",
            "recipient_email": "x@y.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_schedule_wrong_analysis(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    _, token = await _make_user(db_session, fake_redis, sub="sub-wrong-analysis")

    resp = await client.post(
        "/api/schedules",
        json={
            "analysis_id": str(uuid.uuid4()),
            "cron": _CRON,
            "recipient_email": "x@y.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── 2. GET /api/schedules ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_schedules(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-list")
    analysis = await _make_analysis(db_session, user)

    # Create two schedules
    for i in range(2):
        await client.post(
            "/api/schedules",
            json={
                "analysis_id": str(analysis.id),
                "cron": _CRON,
                "time_window_days": i + 3,
                "recipient_email": f"user{i}@example.com",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/api/schedules", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_schedules_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Users must not see each other's schedules."""
    user_a, token_a = await _make_user(db_session, fake_redis, sub="sub-iso-a")
    user_b, token_b = await _make_user(db_session, fake_redis, sub="sub-iso-b")

    analysis_a = await _make_analysis(db_session, user_a)
    await client.post(
        "/api/schedules",
        json={
            "analysis_id": str(analysis_a.id),
            "cron": _CRON,
            "recipient_email": "a@example.com",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp_b = await client.get(
        "/api/schedules", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp_b.json() == []


# ── 3. PATCH /api/schedules/{id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_schedule(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-update")
    analysis = await _make_analysis(db_session, user)

    create_resp = await client.post(
        "/api/schedules",
        json={
            "analysis_id": str(analysis.id),
            "cron": _CRON,
            "recipient_email": "orig@example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    sched_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/schedules/{sched_id}",
        json={"is_active": False, "recipient_email": "new@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["is_active"] is False
    assert data["recipient_email"] == "new@example.com"


@pytest.mark.asyncio
async def test_update_schedule_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user_a, token_a = await _make_user(db_session, fake_redis, sub="sub-upd-a")
    _, token_b = await _make_user(db_session, fake_redis, sub="sub-upd-b")
    analysis = await _make_analysis(db_session, user_a)

    create_resp = await client.post(
        "/api/schedules",
        json={"analysis_id": str(analysis.id), "cron": _CRON, "recipient_email": "a@a.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    sched_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/schedules/{sched_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


# ── 4. DELETE /api/schedules/{id} ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_schedule(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-del")
    analysis = await _make_analysis(db_session, user)

    create_resp = await client.post(
        "/api/schedules",
        json={"analysis_id": str(analysis.id), "cron": _CRON, "recipient_email": "d@d.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    sched_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/schedules/{sched_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        "/api/schedules", headers={"Authorization": f"Bearer {token}"}
    )
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_delete_schedule_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user_a, token_a = await _make_user(db_session, fake_redis, sub="sub-del-a")
    _, token_b = await _make_user(db_session, fake_redis, sub="sub-del-b")
    analysis = await _make_analysis(db_session, user_a)

    create_resp = await client.post(
        "/api/schedules",
        json={"analysis_id": str(analysis.id), "cron": _CRON, "recipient_email": "a@a.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    sched_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/schedules/{sched_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


# ── 5. Schedule service helpers ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compute_next_run_returns_future_date() -> None:
    from app.services.schedule_service import compute_next_run

    next_run = compute_next_run("0 8 * * 1")
    assert next_run > datetime.now(UTC)


@pytest.mark.asyncio
async def test_get_due_schedules(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    from datetime import timedelta

    from app.services.schedule_service import get_due_schedules

    user = await auth_service.upsert_user(
        db_session,
        sub="sub-due",
        provider="oidc",
        email="due@example.com",
        display_name="Due User",
    )
    analysis = await _make_analysis(db_session, user)

    past = datetime.now(UTC) - timedelta(minutes=5)
    future = datetime.now(UTC) + timedelta(hours=1)

    s_due = Schedule(
        user_id=user.id,
        analysis_id=analysis.id,
        cron=_CRON,
        recipient_email="due@example.com",
        next_run_at=past,
    )
    s_not_due = Schedule(
        user_id=user.id,
        analysis_id=analysis.id,
        cron=_CRON,
        recipient_email="notdue@example.com",
        next_run_at=future,
    )
    db_session.add_all([s_due, s_not_due])
    await db_session.commit()

    due = await get_due_schedules(db_session)
    due_ids = {s.id for s in due}
    assert s_due.id in due_ids
    assert s_not_due.id not in due_ids
