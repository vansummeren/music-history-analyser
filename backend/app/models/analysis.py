from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.ai_config import AIConfig
from app.models.spotify_account import SpotifyAccount
from app.models.user import User

RunStatus = Literal["pending", "running", "completed", "failed"]


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    spotify_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spotify_accounts.id", ondelete="CASCADE")
    )
    ai_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_configs.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship("User", lazy="raise")
    spotify_account: Mapped[SpotifyAccount] = relationship("SpotifyAccount", lazy="raise")
    ai_config: Mapped[AIConfig] = relationship("AIConfig", lazy="raise")
    runs: Mapped[list[AnalysisRun]] = relationship(
        "AnalysisRun", back_populates="analysis", lazy="raise"
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    analysis: Mapped[Analysis] = relationship("Analysis", back_populates="runs", lazy="raise")
