"""Pydantic schemas for admin endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Request bodies ────────────────────────────────────────────────────────────


class TestEmailRequest(BaseModel):
    recipient: str


class TestAIRequest(BaseModel):
    prompt: str = "Say hello and confirm you are working correctly."


# ── Response bodies ───────────────────────────────────────────────────────────


class TestEmailResponse(BaseModel):
    message: str
    recipient: str


class TrackItem(BaseModel):
    title: str
    artist: str
    album: str
    played_at: str


class TestSpotifyResponse(BaseModel):
    account_id: uuid.UUID
    display_name: str | None
    tracks: list[TrackItem]
    count: int


class TableRow(BaseModel):
    table: str
    row_count: int


class TablesResponse(BaseModel):
    tables: list[TableRow]


class TestAIResponse(BaseModel):
    config_id: uuid.UUID
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    text: str


# ── Admin user list / detail ──────────────────────────────────────────────────


class AdminUserSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    display_name: str | None
    email: str | None
    role: str
    created_at: datetime
    spotify_accounts_count: int
    analyses_count: int
    schedules_count: int
    play_events_count: int


class AdminSpotifyAccountSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    spotify_user_id: str
    display_name: str | None
    polling_enabled: bool
    last_polled_at: datetime | None
    play_events_count: int


class AdminAnalysisSummary(BaseModel):
    id: uuid.UUID
    name: str
    prompt: str
    run_count: int
    last_run_at: datetime | None
    last_run_status: str | None


class AdminScheduleSummary(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    analysis_name: str | None
    cron: str
    time_window_days: int
    recipient_email: str
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime


class AdminUserDetail(BaseModel):
    id: uuid.UUID
    display_name: str | None
    email: str | None
    role: str
    created_at: datetime
    spotify_accounts: list[AdminSpotifyAccountSummary]
    analyses: list[AdminAnalysisSummary]
    schedules: list[AdminScheduleSummary]


# ── Application logs ──────────────────────────────────────────────────────────


class AppLogRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    created_at: datetime
    level: str
    service: str
    logger_name: str
    message: str


class AppLogsResponse(BaseModel):
    total: int
    items: list[AppLogRead]


# ── Database statistics ───────────────────────────────────────────────────────


class TableSizeRow(BaseModel):
    table: str
    row_count: int
    # Sizes in bytes; None when the backend DB is not PostgreSQL
    total_size_bytes: int | None = None
    table_size_bytes: int | None = None
    index_size_bytes: int | None = None


class DbStatsResponse(BaseModel):
    # Total database size in bytes; None for non-PostgreSQL backends
    database_size_bytes: int | None = None
    tables: list[TableSizeRow]
    log_retention_days: int = Field(
        description="Configured log-retention period in days"
    )
