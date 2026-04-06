"""Pydantic schemas for Spotify resources."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PollScheduleRule(BaseModel):
    """One time-window rule in a per-account polling schedule.

    *days* is a list of ISO weekday numbers (0 = Monday … 6 = Sunday).
    *start_hour* (inclusive) and *end_hour* (exclusive) define a UTC hour
    window.  Use ``end_hour=24`` to mean "until midnight".
    """

    days: list[int] = Field(
        ..., description="Weekday numbers (0=Mon … 6=Sun)"
    )
    start_hour: int = Field(..., ge=0, le=23, description="Window start hour (UTC, inclusive)")
    end_hour: int = Field(..., ge=1, le=24, description="Window end hour (UTC, exclusive)")
    interval_minutes: int = Field(..., ge=1, le=1440, description="Polling interval in minutes")


class SpotifyAccountRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    spotify_user_id: str
    display_name: str | None = None
    email: str | None = None
    scopes: str
    poll_interval_minutes: int
    polling_enabled: bool
    last_polled_at: datetime | None = None
    poll_schedule: list[Any] | None = None
    created_at: datetime


class SpotifyAccountPollUpdate(BaseModel):
    """Payload for updating the polling configuration of a linked Spotify account."""

    poll_interval_minutes: int | None = Field(
        default=None, ge=1, le=1440, description="Default polling interval in minutes (1–1440)"
    )
    polling_enabled: bool | None = None
    # Pass an empty list to clear the schedule and revert to the simple interval.
    poll_schedule: list[PollScheduleRule] | None = None


class TrackRead(BaseModel):
    title: str
    artist: str
    album: str
    played_at: datetime


class PlayEventRead(BaseModel):
    """A single play event from the shadow listening-history database."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    streaming_account_id: uuid.UUID
    track_provider: str
    track_external_id: str
    played_at: datetime
    created_at: datetime

    # Denormalised track fields for convenience (populated by the router)
    track_title: str = ""
    track_artist: str = ""
    track_album: str = ""


class SpotifyLinkResponse(BaseModel):
    auth_url: str
