from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import User


class SpotifyAccount(Base):
    __tablename__ = "spotify_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    spotify_user_id: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Fernet-encrypted tokens (stored as base64 strings)
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str] = mapped_column(Text, default="")

    # ── Polling configuration ──────────────────────────────────────────────────
    # How often (in minutes) to automatically poll recently-played history.
    # Default: 60 minutes.  Range enforced in the API layer (1–1440).
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    # Set to False to pause automatic polling for this account without deleting it.
    polling_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Timestamp of the last successful poll (used as the ``after`` cursor for the
    # Spotify recently-played endpoint to avoid re-importing duplicate events).
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # Optional time-window schedule that overrides ``poll_interval_minutes``.
    # When set, each rule is evaluated against the current UTC day/hour to
    # determine the effective polling interval.
    # Schema: list of {days: int[], start_hour: int, end_hour: int, interval_minutes: int}
    # days: 0=Mon … 6=Sun; end_hour is exclusive (24 = end of day).
    poll_schedule: Mapped[list[Any] | None] = mapped_column(
        JSON, nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationship back to the owning User (lazy="raise" to avoid N+1 surprises)
    user: Mapped[User] = relationship("User", lazy="raise")
