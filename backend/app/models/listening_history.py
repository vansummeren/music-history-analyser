"""Generic listening-history ORM models.

These models are intentionally provider-agnostic so that they can be re-used
for Spotify, YouTube, or any other streaming service in the future.

Primary-key design
------------------
Artists, albums, and tracks use a composite primary key of
``(provider, external_id)`` where *provider* is a short lowercase string
(e.g. ``"spotify"``, ``"youtube"``) and *external_id* is the service's own
identifier (e.g. the Spotify base-62 artist/track ID).

Media type
----------
The ``Track`` model carries a ``media_type`` column (``"track"`` | ``"video"``
| …) so that future video content from YouTube or elsewhere can be stored in
the same table without schema changes.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Artist(Base):
    """A music artist or content creator, keyed by provider + external ID."""

    __tablename__ = "artists"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    track_links: Mapped[list[TrackArtist]] = relationship(
        "TrackArtist", back_populates="artist", lazy="raise"
    )


class Album(Base):
    """A release (album, EP, single, …), keyed by provider + external ID."""

    __tablename__ = "albums"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    tracks: Mapped[list[Track]] = relationship(
        "Track", back_populates="album", lazy="raise"
    )


class Track(Base):
    """A playable media item (track or video), keyed by provider + external ID."""

    __tablename__ = "tracks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["album_provider", "album_external_id"],
            ["albums.provider", "albums.external_id"],
            ondelete="SET NULL",
        ),
    )

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))

    # Optional album link (videos may not have an album)
    album_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    album_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "track" | "video" | … – extensible without schema changes
    media_type: Mapped[str] = mapped_column(String(50), default="track")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    album: Mapped[Album | None] = relationship(
        "Album",
        back_populates="tracks",
        lazy="raise",
        foreign_keys=[album_provider, album_external_id],
    )
    artist_links: Mapped[list[TrackArtist]] = relationship(
        "TrackArtist", back_populates="track", lazy="raise"
    )
    play_events: Mapped[list[PlayEvent]] = relationship(
        "PlayEvent", back_populates="track", lazy="raise"
    )


class TrackArtist(Base):
    """Many-to-many junction between tracks and artists."""

    __tablename__ = "track_artists"
    __table_args__ = (
        ForeignKeyConstraint(
            ["track_provider", "track_external_id"],
            ["tracks.provider", "tracks.external_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["artist_provider", "artist_external_id"],
            ["artists.provider", "artists.external_id"],
            ondelete="CASCADE",
        ),
    )

    track_provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    track_external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    artist_provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    artist_external_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Relationships
    track: Mapped[Track] = relationship(
        "Track",
        back_populates="artist_links",
        lazy="raise",
        foreign_keys=[track_provider, track_external_id],
    )
    artist: Mapped[Artist] = relationship(
        "Artist",
        back_populates="track_links",
        lazy="raise",
        foreign_keys=[artist_provider, artist_external_id],
    )


class PlayEvent(Base):
    """A single play event — one row per (streaming_account, track, played_at) triple.

    The unique constraint on ``(streaming_account_id, track_provider,
    track_external_id, played_at)`` prevents duplicate imports when the same
    recently-played window is polled multiple times.
    """

    __tablename__ = "play_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["track_provider", "track_external_id"],
            ["tracks.provider", "tracks.external_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "streaming_account_id",
            "track_provider",
            "track_external_id",
            "played_at",
            name="uq_play_events_account_track_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # FK to the streaming_account that owns this history row (e.g. a SpotifyAccount)
    streaming_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spotify_accounts.id", ondelete="CASCADE")
    )
    track_provider: Mapped[str] = mapped_column(String(50))
    track_external_id: Mapped[str] = mapped_column(String(255))
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    track: Mapped[Track] = relationship(
        "Track",
        back_populates="play_events",
        lazy="raise",
        foreign_keys=[track_provider, track_external_id],
    )


# ── Polling configuration (stored on SpotifyAccount, see spotify_account.py) ─
# poll_interval_minutes  – how often (in minutes) to poll for new history
# polling_enabled        – whether automatic polling is active for this account
# last_polled_at         – timestamp of the last successful poll (used to
#                          set the Spotify API ``after`` cursor)
#
# These columns live on the streaming-account model so that each account can
# have its own independent polling schedule.
