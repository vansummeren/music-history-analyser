"""Diagnostic and admin router."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy import table as sa_table
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.ai_config import AIConfig
from app.models.analysis import Analysis, AnalysisRun
from app.models.listening_history import PlayEvent
from app.models.schedule import Schedule
from app.models.spotify_account import SpotifyAccount
from app.models.user import User
from app.schemas.admin import (
    AdminAnalysisSummary,
    AdminScheduleSummary,
    AdminSpotifyAccountSummary,
    AdminUserDetail,
    AdminUserSummary,
    TableRow,
    TablesResponse,
    TestAIRequest,
    TestAIResponse,
    TestEmailRequest,
    TestEmailResponse,
    TestSpotifyResponse,
    TrackItem,
)
from app.services import crypto
from app.services.ai.base import AIProvider
from app.services.ai.claude import ClaudeAdapter
from app.services.ai.perplexity import PerplexityAdapter
from app.services.email_service import send_test_email
from app.services.music.spotify import SpotifyAdapter

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_ai_adapter(provider: str) -> AIProvider:
    if provider == "claude":
        return ClaudeAdapter()
    if provider == "perplexity":
        return PerplexityAdapter()
    raise ValueError(f"Unknown AI provider: {provider!r}")


# ── GET /api/admin/tables ─────────────────────────────────────────────────────

_ADMIN_TABLES = [
    "users",
    "spotify_accounts",
    "ai_configs",
    "analyses",
    "analysis_runs",
    "schedules",
    "artists",
    "albums",
    "tracks",
    "play_events",
]


@router.get("/tables", response_model=TablesResponse)
async def get_tables(
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TablesResponse:
    """Return row counts for all main database tables (admin only)."""
    rows: list[TableRow] = []
    for table_name in _ADMIN_TABLES:
        result = await db.execute(select(func.count()).select_from(sa_table(table_name)))
        count: int = result.scalar_one()
        rows.append(TableRow(table=table_name, row_count=count))
    return TablesResponse(tables=rows)


# ── POST /api/admin/test-email ────────────────────────────────────────────────


@router.post("/test-email", response_model=TestEmailResponse)
async def test_email(
    body: TestEmailRequest,
    user: User = Depends(get_current_user),
) -> TestEmailResponse:
    """Send a test email to verify that the SMTP configuration is working."""
    await send_test_email(recipient=body.recipient)
    return TestEmailResponse(
        message=f"Test email sent to {body.recipient}",
        recipient=body.recipient,
    )


# ── POST /api/admin/test-spotify/{account_id} ─────────────────────────────────


@router.post(
    "/test-spotify/{account_id}",
    response_model=TestSpotifyResponse,
)
async def test_spotify(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestSpotifyResponse:
    """Fetch the 10 most recently played tracks for a Spotify account.

    The account must belong to the authenticated user.
    """
    account = await db.get(SpotifyAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Spotify account not found"
        )
    if account.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this Spotify account",
        )

    access_token = crypto.decrypt(account.encrypted_access_token)
    refresh_token = crypto.decrypt(account.encrypted_refresh_token)

    now = datetime.now(UTC)
    expires_at = account.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= now:
        adapter = SpotifyAdapter()
        access_token, new_refresh, new_expires = await adapter.refresh_token(refresh_token)
        account.encrypted_access_token = crypto.encrypt(access_token)
        account.encrypted_refresh_token = crypto.encrypt(new_refresh)
        account.token_expires_at = new_expires
        await db.commit()

    adapter = SpotifyAdapter()
    tracks = await adapter.get_recently_played(access_token, limit=10)

    return TestSpotifyResponse(
        account_id=account.id,
        display_name=account.display_name,
        tracks=[
            TrackItem(
                title=t.title,
                artist=t.artist,
                album=t.album,
                played_at=t.played_at.isoformat(),
            )
            for t in tracks
        ],
        count=len(tracks),
    )


# ── POST /api/admin/test-ai/{config_id} ──────────────────────────────────────


@router.post("/test-ai/{config_id}", response_model=TestAIResponse)
async def test_ai(
    config_id: uuid.UUID,
    body: TestAIRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestAIResponse:
    """Send a test prompt to the configured AI provider.

    The AI config must belong to the authenticated user.
    """
    result = await db.execute(select(AIConfig).where(AIConfig.id == config_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI config not found"
        )
    if config.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this AI config",
        )

    api_key = crypto.decrypt(config.encrypted_api_key)
    adapter = _get_ai_adapter(config.provider)
    ai_result = await adapter.analyse(
        api_key=api_key,
        prompt=body.prompt,
        track_list="(connectivity test — no tracks)",
    )

    return TestAIResponse(
        config_id=config.id,
        provider=config.provider,
        model=ai_result.model,
        input_tokens=ai_result.input_tokens,
        output_tokens=ai_result.output_tokens,
        text=ai_result.text,
    )


# ── GET /api/admin/users ──────────────────────────────────────────────────────


@router.get("/users", response_model=list[AdminUserSummary])
async def list_users(
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserSummary]:
    """Return a summary of all users (admin only)."""
    # Build per-user counts in a single query using correlated subqueries.
    spotify_sub = (
        select(func.count())
        .select_from(SpotifyAccount)
        .where(SpotifyAccount.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    analyses_sub = (
        select(func.count())
        .select_from(Analysis)
        .where(Analysis.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    schedules_sub = (
        select(func.count())
        .select_from(Schedule)
        .where(Schedule.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    # Play events are linked via spotify_accounts; use a two-level subquery.
    pe_account_sub = (
        select(SpotifyAccount.id).where(SpotifyAccount.user_id == User.id).correlate(User)
    )
    play_events_sub = (
        select(func.count())
        .select_from(PlayEvent)
        .where(PlayEvent.streaming_account_id.in_(pe_account_sub))
        .correlate(User)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            User,
            spotify_sub.label("spotify_accounts_count"),
            analyses_sub.label("analyses_count"),
            schedules_sub.label("schedules_count"),
            play_events_sub.label("play_events_count"),
        ).order_by(User.created_at)
    )

    return [
        AdminUserSummary(
            id=u.id,
            display_name=u.display_name,
            email=u.email,
            role=u.role,
            created_at=u.created_at,
            spotify_accounts_count=int(sa_count),
            analyses_count=int(an_count),
            schedules_count=int(sc_count),
            play_events_count=int(pe_count),
        )
        for u, sa_count, an_count, sc_count, pe_count in result.all()
    ]


# ── GET /api/admin/users/{user_id} ────────────────────────────────────────────


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    _user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    """Return detailed information about a user (admin only)."""
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Spotify accounts with play-event counts in one query per account (JOIN).
    pe_count_sub = (
        select(func.count())
        .select_from(PlayEvent)
        .where(PlayEvent.streaming_account_id == SpotifyAccount.id)
        .correlate(SpotifyAccount)
        .scalar_subquery()
    )
    accounts_result = await db.execute(
        select(SpotifyAccount, pe_count_sub.label("play_events_count"))
        .where(SpotifyAccount.user_id == user_id)
        .order_by(SpotifyAccount.id)
    )
    spotify_summaries: list[AdminSpotifyAccountSummary] = [
        AdminSpotifyAccountSummary(
            id=acc.id,
            spotify_user_id=acc.spotify_user_id,
            display_name=acc.display_name,
            polling_enabled=acc.polling_enabled,
            last_polled_at=acc.last_polled_at,
            play_events_count=int(pe_count),
        )
        for acc, pe_count in accounts_result.all()
    ]

    # Analyses: run count + latest run info, fetched with subqueries.
    run_count_sub = (
        select(func.count())
        .select_from(AnalysisRun)
        .where(AnalysisRun.analysis_id == Analysis.id)
        .correlate(Analysis)
        .scalar_subquery()
    )
    latest_run_at_sub = (
        select(AnalysisRun.created_at)
        .where(AnalysisRun.analysis_id == Analysis.id)
        .correlate(Analysis)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    latest_run_status_sub = (
        select(AnalysisRun.status)
        .where(AnalysisRun.analysis_id == Analysis.id)
        .correlate(Analysis)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    analyses_result = await db.execute(
        select(
            Analysis,
            run_count_sub.label("run_count"),
            latest_run_at_sub.label("last_run_at"),
            latest_run_status_sub.label("last_run_status"),
        )
        .where(Analysis.user_id == user_id)
        .order_by(Analysis.created_at)
    )
    analysis_summaries: list[AdminAnalysisSummary] = [
        AdminAnalysisSummary(
            id=an.id,
            name=an.name,
            prompt=an.prompt,
            run_count=int(run_count),
            last_run_at=last_run_at,
            last_run_status=last_run_status,
        )
        for an, run_count, last_run_at, last_run_status in analyses_result.all()
    ]

    # Schedules joined with their analysis name in one query.
    schedules_result = await db.execute(
        select(Schedule, Analysis.name.label("analysis_name"))
        .join(Analysis, Analysis.id == Schedule.analysis_id, isouter=True)
        .where(Schedule.user_id == user_id)
        .order_by(Schedule.created_at)
    )
    schedule_summaries: list[AdminScheduleSummary] = [
        AdminScheduleSummary(
            id=sc.id,
            analysis_id=sc.analysis_id,
            analysis_name=analysis_name,
            cron=sc.cron,
            time_window_days=sc.time_window_days,
            recipient_email=sc.recipient_email,
            is_active=sc.is_active,
            last_run_at=sc.last_run_at,
            next_run_at=sc.next_run_at,
        )
        for sc, analysis_name in schedules_result.all()
    ]

    return AdminUserDetail(
        id=u.id,
        display_name=u.display_name,
        email=u.email,
        role=u.role,
        created_at=u.created_at,
        spotify_accounts=spotify_summaries,
        analyses=analysis_summaries,
        schedules=schedule_summaries,
    )
