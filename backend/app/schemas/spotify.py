"""Pydantic schemas for Spotify resources."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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
    created_at: datetime


class SpotifyAccountPollUpdate(BaseModel):
    """Payload for updating the polling configuration of a linked Spotify account."""

    poll_interval_minutes: int | None = Field(
        default=None, ge=1, le=1440, description="Polling interval in minutes (1–1440)"
    )
    polling_enabled: bool | None = None


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
