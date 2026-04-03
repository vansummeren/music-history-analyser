"""Tests for Session 04 — Analysis endpoints and analysis service."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.models.analysis import Analysis, AnalysisRun
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.services import auth_service, crypto
from app.services.ai.base import AnalysisResult
from app.services.music.base import TopArtist, TopTrack
from tests.conftest import FakeRedis

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    redis: FakeRedis,
    *,
    sub: str = "analysis-sub",
) -> tuple[User, str]:
    user = await auth_service.upsert_user(
        db, sub=sub, provider="oidc", email="user@example.com", display_name="Test"
    )
    token = auth_service.create_access_token(user.id)
    return user, token


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


async def _make_spotify_account(db: AsyncSession, user: User) -> SpotifyAccount:
    account = SpotifyAccount(
        user_id=user.id,
        spotify_user_id="spotify-analysis-user",
        display_name="Test Spotify",
        email="test@example.com",
        encrypted_access_token=crypto.encrypt("access-token"),
        encrypted_refresh_token=crypto.encrypt("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes="user-read-recently-played user-top-read",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _make_analysis(
    db: AsyncSession,
    user: User,
    spotify_account: SpotifyAccount,
    ai_config: AIConfig,
) -> Analysis:
    analysis = Analysis(
        user_id=user.id,
        spotify_account_id=spotify_account.id,
        ai_config_id=ai_config.id,
        name="My Analysis",
        prompt="Describe my music taste.",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


# ── 1. POST /api/analyses ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_analysis(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis)
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)

    resp = await client.post(
        "/api/analyses",
        json={
            "name": "Test Analysis",
            "spotify_account_id": str(account.id),
            "ai_config_id": str(ai_config.id),
            "prompt": "What is my music taste?",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Analysis"
    assert data["prompt"] == "What is my music taste?"


@pytest.mark.asyncio
async def test_create_analysis_wrong_spotify_account(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Creating an analysis with another user's Spotify account must return 404."""
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-an")
    other, other_token = await _make_user(db_session, fake_redis, sub="other-an")
    account = await _make_spotify_account(db_session, owner)
    ai_config = await _make_ai_config(db_session, other)

    resp = await client.post(
        "/api/analyses",
        json={
            "name": "Bad Analysis",
            "spotify_account_id": str(account.id),
            "ai_config_id": str(ai_config.id),
            "prompt": "test",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_analysis_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/analyses",
        json={
            "name": "x",
            "spotify_account_id": str(uuid.uuid4()),
            "ai_config_id": str(uuid.uuid4()),
            "prompt": "x",
        },
    )
    assert resp.status_code == 401


# ── 2. GET /api/analyses ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_analyses(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-list-an")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    await _make_analysis(db_session, user, account, ai_config)

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_analyses_isolated_per_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user_a, token_a = await _make_user(db_session, fake_redis, sub="sub-a-an")
    user_b, token_b = await _make_user(db_session, fake_redis, sub="sub-b-an")
    account = await _make_spotify_account(db_session, user_a)
    ai_config = await _make_ai_config(db_session, user_a)
    await _make_analysis(db_session, user_a, account, ai_config)

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert resp.json() == []


# ── 3. DELETE /api/analyses/{id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_analysis(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-del-an")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    resp = await client.delete(
        f"/api/analyses/{analysis.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    deleted = await db_session.get(Analysis, analysis.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_delete_analysis_forbidden_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-del-an")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-del-an")
    account = await _make_spotify_account(db_session, owner)
    ai_config = await _make_ai_config(db_session, owner)
    analysis = await _make_analysis(db_session, owner, account, ai_config)

    resp = await client.delete(
        f"/api/analyses/{analysis.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


# ── 4. POST /api/analyses/{id}/run ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_run_success(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-run")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    mock_tracks = [
        TopTrack(
            external_id="track-a",
            title="Song A",
            artist="Artist A",
            album="Album A",
        )
    ]
    mock_artists = [
        TopArtist(
            external_id="artist-a",
            name="Artist A",
            genres=["pop"],
        )
    ]
    mock_result = AnalysisResult(
        text="You enjoy pop music.",
        model="claude-3-5-haiku-20241022",
        input_tokens=100,
        output_tokens=50,
    )

    with (
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_tracks",
            AsyncMock(return_value=mock_tracks),
        ),
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_artists",
            AsyncMock(return_value=mock_artists),
        ),
        patch(
            "app.services.analysis_service.ClaudeAdapter.analyse",
            AsyncMock(return_value=mock_result),
        ),
    ):
        resp = await client.post(
            f"/api/analyses/{analysis.id}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result_text"] == "You enjoy pop music."
    assert data["model"] == "claude-3-5-haiku-20241022"
    assert data["input_tokens"] == 100
    assert data["output_tokens"] == 50


@pytest.mark.asyncio
async def test_trigger_run_ai_failure_stored_as_failed(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-run-fail")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    with (
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_tracks",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_artists",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.analysis_service.ClaudeAdapter.analyse",
            AsyncMock(side_effect=Exception("API error")),
        ),
    ):
        resp = await client.post(
            f"/api/analyses/{analysis.id}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "failed"
    assert "API error" in data["error"]


@pytest.mark.asyncio
async def test_trigger_run_forbidden_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-run")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-run")
    account = await _make_spotify_account(db_session, owner)
    ai_config = await _make_ai_config(db_session, owner)
    analysis = await _make_analysis(db_session, owner, account, ai_config)

    resp = await client.post(
        f"/api/analyses/{analysis.id}/run",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


# ── 5. GET /api/analyses/{id}/runs ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_runs(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-list-runs")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    # Create a run directly in the DB
    run = AnalysisRun(
        analysis_id=analysis.id,
        status="completed",
        result_text="Great music!",
        model="claude-3-5-haiku-20241022",
        input_tokens=50,
        output_tokens=20,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(run)
    await db_session.commit()

    resp = await client.get(
        f"/api/analyses/{analysis.id}/runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["result_text"] == "Great music!"


# ── 6. GET /api/analyses/{id}/runs/{run_id} ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_run(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-get-run")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    run = AnalysisRun(
        analysis_id=analysis.id,
        status="completed",
        result_text="Jazz and blues!",
        model="claude-3-5-haiku-20241022",
        input_tokens=60,
        output_tokens=30,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    resp = await client.get(
        f"/api/analyses/{analysis.id}/runs/{run.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result_text"] == "Jazz and blues!"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_run_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    user, token = await _make_user(db_session, fake_redis, sub="sub-get-run-404")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    resp = await client.get(
        f"/api/analyses/{analysis.id}/runs/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── 7. Partial failure resilience ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_succeeds_when_top_tracks_fail(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Analysis should still complete when fetching top tracks fails."""
    user, token = await _make_user(db_session, fake_redis, sub="sub-partial-tracks")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    mock_artists = [
        TopArtist(external_id="artist-a", name="Artist A", genres=["pop"]),
    ]
    mock_result = AnalysisResult(
        text="Based on your artists, you enjoy pop.",
        model="claude-3-5-haiku-20241022",
        input_tokens=80,
        output_tokens=40,
    )

    with (
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_tracks",
            AsyncMock(side_effect=Exception("Spotify tracks API error")),
        ),
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_artists",
            AsyncMock(return_value=mock_artists),
        ),
        patch(
            "app.services.analysis_service.ClaudeAdapter.analyse",
            AsyncMock(return_value=mock_result),
        ),
    ):
        resp = await client.post(
            f"/api/analyses/{analysis.id}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "completed"
    assert "Could not fetch top tracks" in data["result_text"]
    assert "Based on your artists" in data["result_text"]


@pytest.mark.asyncio
async def test_run_succeeds_when_top_artists_fail(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Analysis should still complete when fetching top artists fails."""
    user, token = await _make_user(db_session, fake_redis, sub="sub-partial-artists")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    mock_tracks = [
        TopTrack(
            external_id="track-a",
            title="Song A",
            artist="Artist A",
            album="Album A",
        ),
    ]
    mock_result = AnalysisResult(
        text="Based on your tracks, you enjoy rock.",
        model="claude-3-5-haiku-20241022",
        input_tokens=80,
        output_tokens=40,
    )

    with (
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_tracks",
            AsyncMock(return_value=mock_tracks),
        ),
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_artists",
            AsyncMock(side_effect=Exception("Spotify artists API error")),
        ),
        patch(
            "app.services.analysis_service.ClaudeAdapter.analyse",
            AsyncMock(return_value=mock_result),
        ),
    ):
        resp = await client.post(
            f"/api/analyses/{analysis.id}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "completed"
    assert "Could not fetch top artists" in data["result_text"]
    assert "Based on your tracks" in data["result_text"]


@pytest.mark.asyncio
async def test_run_succeeds_when_both_fetches_fail_but_ai_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Analysis should still complete even if both data fetches fail."""
    user, token = await _make_user(db_session, fake_redis, sub="sub-partial-both")
    account = await _make_spotify_account(db_session, user)
    ai_config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, ai_config)

    mock_result = AnalysisResult(
        text="Not enough data for a full analysis.",
        model="claude-3-5-haiku-20241022",
        input_tokens=40,
        output_tokens=20,
    )

    with (
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_tracks",
            AsyncMock(side_effect=Exception("tracks error")),
        ),
        patch(
            "app.services.analysis_service.SpotifyAdapter.get_top_artists",
            AsyncMock(side_effect=Exception("artists error")),
        ),
        patch(
            "app.services.analysis_service.ClaudeAdapter.analyse",
            AsyncMock(return_value=mock_result),
        ),
    ):
        resp = await client.post(
            f"/api/analyses/{analysis.id}/run",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "completed"
    assert "Could not fetch top tracks" in data["result_text"]
    assert "Could not fetch top artists" in data["result_text"]
    assert "Not enough data" in data["result_text"]


# ── PATCH /api/analyses/{analysis_id} ────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_analysis_name_and_prompt(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Owner can update the name and prompt of an analysis."""
    user, token = await _make_user(db_session, fake_redis, sub="upd-analysis-sub")
    account = await _make_spotify_account(db_session, user)
    config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, config)

    resp = await client.patch(
        f"/api/analyses/{analysis.id}",
        json={"name": "Updated Name", "prompt": "New prompt text"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["prompt"] == "New prompt text"


@pytest.mark.asyncio
async def test_update_analysis_partial(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Partial updates (only name) are supported."""
    user, token = await _make_user(db_session, fake_redis, sub="upd-partial-sub")
    account = await _make_spotify_account(db_session, user)
    config = await _make_ai_config(db_session, user)
    analysis = await _make_analysis(db_session, user, account, config)
    original_prompt = analysis.prompt

    resp = await client.patch(
        f"/api/analyses/{analysis.id}",
        json={"name": "Only Name Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Only Name Updated"
    assert data["prompt"] == original_prompt


@pytest.mark.asyncio
async def test_update_analysis_forbidden_for_other_user(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Users cannot update analyses belonging to other users."""
    owner, _ = await _make_user(db_session, fake_redis, sub="owner-upd")
    _, other_token = await _make_user(db_session, fake_redis, sub="other-upd")
    account = await _make_spotify_account(db_session, owner)
    config = await _make_ai_config(db_session, owner)
    analysis = await _make_analysis(db_session, owner, account, config)

    resp = await client.patch(
        f"/api/analyses/{analysis.id}",
        json={"name": "Stolen Name"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_analysis_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> None:
    """Returns 404 when the analysis does not exist."""
    _, token = await _make_user(db_session, fake_redis, sub="404-upd-sub")
    resp = await client.patch(
        f"/api/analyses/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
