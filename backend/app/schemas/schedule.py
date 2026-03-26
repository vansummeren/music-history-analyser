"""Pydantic schemas for Schedule resources."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class ScheduleCreate(BaseModel):
    analysis_id: uuid.UUID
    cron: str
    time_window_days: int = 7
    recipient_email: str

    @field_validator("time_window_days")
    @classmethod
    def validate_time_window(cls, v: int) -> int:
        if v < 1 or v > 365:
            raise ValueError("time_window_days must be between 1 and 365")
        return v

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        from croniter import CroniterBadCronError, croniter  # type: ignore[import-untyped]

        try:
            croniter(v)
        except (CroniterBadCronError, Exception) as exc:
            raise ValueError(f"Invalid cron expression: {exc}") from exc
        return v


class ScheduleUpdate(BaseModel):
    cron: str | None = None
    time_window_days: int | None = None
    recipient_email: str | None = None
    is_active: bool | None = None

    @field_validator("time_window_days")
    @classmethod
    def validate_time_window(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 365):
            raise ValueError("time_window_days must be between 1 and 365")
        return v

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from croniter import CroniterBadCronError, croniter

        try:
            croniter(v)
        except (CroniterBadCronError, Exception) as exc:
            raise ValueError(f"Invalid cron expression: {exc}") from exc
        return v


class ScheduleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    analysis_id: uuid.UUID
    cron: str
    time_window_days: int
    recipient_email: str
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime
