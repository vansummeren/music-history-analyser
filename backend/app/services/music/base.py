"""Abstract base class for music provider adapters.

To add a new music provider, subclass MusicProvider and implement all abstract methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Artist:
    """Represents a single artist (from any source)."""

    external_id: str
    name: str
    provider: str = "spotify"


@dataclass
class Album:
    """Represents an album or release."""

    external_id: str
    title: str
    provider: str = "spotify"


@dataclass
class Track:
    """Represents a single played/listed track."""

    title: str
    artist: str  # Comma-separated display string (kept for backward compat)
    album: str  # Display string (kept for backward compat)
    played_at: datetime

    # Rich structured fields populated when fetching history for DB storage
    external_id: str = ""
    provider: str = "spotify"
    album_obj: Album | None = None
    artist_objs: list[Artist] = field(default_factory=list)
    duration_ms: int | None = None
    media_type: str = "track"


@dataclass
class TopArtist:
    """Represents a user's top artist."""

    external_id: str
    name: str
    genres: list[str] = field(default_factory=list)
    popularity: int = 0
    provider: str = "spotify"


@dataclass
class TopTrack:
    """Represents a user's top track."""

    external_id: str
    title: str
    artist: str  # Comma-separated display string
    album: str
    popularity: int = 0
    duration_ms: int | None = None
    provider: str = "spotify"


class MusicProvider(ABC):
    """Abstract interface that every music provider adapter must implement."""

    @abstractmethod
    async def get_recently_played(
        self,
        access_token: str,
        *,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[Track]:
        """Return a list of recently played tracks for the given access token."""

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> tuple[str, str, datetime]:
        """Refresh the OAuth access token.

        Returns (new_access_token, new_refresh_token, expires_at).
        """

    @abstractmethod
    async def get_top_tracks(
        self,
        access_token: str,
        *,
        limit: int = 50,
        time_range: str = "medium_term",
    ) -> list[TopTrack]:
        """Return the user's top tracks.

        *time_range* is provider-specific; for Spotify: ``"short_term"`` (4 weeks),
        ``"medium_term"`` (6 months), or ``"long_term"`` (all time).
        """

    @abstractmethod
    async def get_top_artists(
        self,
        access_token: str,
        *,
        limit: int = 50,
        time_range: str = "medium_term",
    ) -> list[TopArtist]:
        """Return the user's top artists.

        *time_range* is provider-specific; for Spotify: ``"short_term"`` (4 weeks),
        ``"medium_term"`` (6 months), or ``"long_term"`` (all time).
        """
