"""Pydantic schemas for admin endpoints."""
from __future__ import annotations

import uuid

from pydantic import BaseModel

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


class TestAIResponse(BaseModel):
    config_id: uuid.UUID
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    text: str
