"""Abstract base class for music provider adapters.

To add a new music provider, subclass MusicProvider and implement all abstract methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Track:
    """Represents a single played track."""

    title: str
    artist: str
    album: str
    played_at: datetime


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
