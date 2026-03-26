"""Pydantic schemas for Analysis and AnalysisRun resources."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnalysisCreate(BaseModel):
    name: str
    spotify_account_id: uuid.UUID
    ai_config_id: uuid.UUID
    prompt: str


class AnalysisRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    spotify_account_id: uuid.UUID
    ai_config_id: uuid.UUID
    name: str
    prompt: str
    created_at: datetime


class AnalysisRunRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    analysis_id: uuid.UUID
    status: str
    result_text: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
