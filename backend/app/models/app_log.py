"""Application-log model — stores structured log records for all services."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppLog(Base):
    """One row per log record emitted by any service (backend, worker, beat …)."""

    __tablename__ = "app_logs"
    __table_args__ = (
        # Speed up the most common admin-panel queries
        Index("ix_app_logs_created_at", "created_at"),
        Index("ix_app_logs_level", "level"),
        Index("ix_app_logs_service", "service"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # Log level as a string: DEBUG, INFO, WARNING, ERROR, CRITICAL
    level: Mapped[str] = mapped_column(String(20))
    # Service that emitted the record (value of SERVICE_NAME env-var)
    service: Mapped[str] = mapped_column(String(100))
    # Dotted Python logger name, e.g. "app.routers.auth"
    logger_name: Mapped[str] = mapped_column(String(255))
    # Formatted message, including exception traceback when present
    message: Mapped[str] = mapped_column(Text)
