"""Pydantic schemas for AI configuration resources."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AIProviderLiteral = Literal["claude", "perplexity"]


class AIConfigCreate(BaseModel):
    provider: AIProviderLiteral
    display_name: str
    api_key: str


class AIConfigRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    display_name: str
    created_at: datetime
