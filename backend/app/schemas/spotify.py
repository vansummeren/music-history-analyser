"""Pydantic schemas for Spotify resources."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SpotifyAccountRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    spotify_user_id: str
    display_name: str | None = None
    email: str | None = None
    scopes: str
    created_at: datetime


class TrackRead(BaseModel):
    title: str
    artist: str
    album: str
    played_at: datetime


class SpotifyLinkResponse(BaseModel):
    auth_url: str
