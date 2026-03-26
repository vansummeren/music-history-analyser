from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

UserRole = Literal["user", "admin"]


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    sub: str
    provider: str
    email: str | None = None
    display_name: str | None = None
    role: UserRole
    created_at: datetime
