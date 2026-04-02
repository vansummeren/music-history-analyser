"""Spotify adapter — implements MusicProvider for the Spotify Web API."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import settings
from app.services.music.base import Album, Artist, MusicProvider, TopArtist, TopTrack, Track

logger = logging.getLogger(__name__)

_SPOTIFY_ACCOUNTS_BASE = "https://accounts.spotify.com"
_SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Scopes requested during OAuth authorisation
SPOTIFY_SCOPES = "user-read-recently-played user-read-email user-top-read"


class SpotifyRateLimitError(Exception):
    """Raised when Spotify returns HTTP 429 Too Many Requests."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Spotify rate limit exceeded; retry after {retry_after}s")


def _check_rate_limit(resp: httpx.Response) -> None:
    """If *resp* is a 429, log the ``Retry-After`` value and raise :exc:`SpotifyRateLimitError`."""
    if resp.status_code != 429:
        return
    retry_after_str = resp.headers.get("Retry-After", "0")
    try:
        parsed = int(retry_after_str)
        if parsed < 0:
            logger.warning(
                "Spotify returned a negative Retry-After value (%d); treating as 0", parsed
            )
        retry_after = max(0, parsed)
    except ValueError:
        retry_after = 0
    logger.warning(
        "Spotify rate limit hit (HTTP 429); Retry-After: %ds — backing off",
        retry_after,
    )
    raise SpotifyRateLimitError(retry_after)


class SpotifyAdapter(MusicProvider):
    """Adapter that wraps the Spotify Web API."""

    async def get_recently_played(
        self,
        access_token: str,
        *,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[Track]:
        """Return recently played tracks from the Spotify Web API.

        *after* and *before* are converted to Unix timestamps in milliseconds
        as required by the Spotify API.  At most 50 items are returned per call.

        Returned ``Track`` objects are enriched with ``external_id``, ``provider``,
        ``album_obj``, and ``artist_objs`` so that the history service can upsert
        them into the normalised database tables without an extra API call.
        """
        params: dict[str, Any] = {"limit": min(limit, 50)}
        if after is not None:
            params["after"] = int(after.timestamp() * 1000)
        if before is not None:
            params["before"] = int(before.timestamp() * 1000)

        logger.debug("Fetching recently played tracks from Spotify (limit=%d)", limit)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_SPOTIFY_API_BASE}/me/player/recently-played",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            _check_rate_limit(resp)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        tracks: list[Track] = []
        for item in data.get("items", []):
            track_obj = item.get("track", {})

            # Build structured artist objects
            artist_objs = [
                Artist(
                    external_id=a.get("id", ""),
                    name=a.get("name", ""),
                    provider="spotify",
                )
                for a in track_obj.get("artists", [])
                if a.get("id")
            ]
            artists_display = ", ".join(a.name for a in artist_objs)

            # Build structured album object
            album_data = track_obj.get("album", {})
            album_obj: Album | None = None
            if album_data.get("id"):
                album_obj = Album(
                    external_id=album_data["id"],
                    title=album_data.get("name", ""),
                    provider="spotify",
                )
            album_display = album_data.get("name", "")

            played_at_str: str = item.get("played_at", "")
            try:
                played_at = datetime.fromisoformat(
                    played_at_str.replace("Z", "+00:00")
                )
            except ValueError:
                played_at = datetime.now(UTC)

            tracks.append(
                Track(
                    title=track_obj.get("name", ""),
                    artist=artists_display,
                    album=album_display,
                    played_at=played_at,
                    external_id=track_obj.get("id", ""),
                    provider="spotify",
                    album_obj=album_obj,
                    artist_objs=artist_objs,
                    duration_ms=track_obj.get("duration_ms"),
                    media_type="track",
                )
            )

        logger.info("Spotify returned %d recently played track(s)", len(tracks))
        return tracks

    async def get_top_tracks(
        self,
        access_token: str,
        *,
        limit: int = 50,
        time_range: str = "medium_term",
    ) -> list[TopTrack]:
        """Return the user's top tracks from Spotify.

        *time_range* must be one of ``"short_term"`` (≈4 weeks),
        ``"medium_term"`` (≈6 months), or ``"long_term"`` (all time).
        """
        logger.debug(
            "Fetching top tracks from Spotify (limit=%d, time_range=%s)", limit, time_range
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_SPOTIFY_API_BASE}/me/top/tracks",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": min(limit, 50), "time_range": time_range},
            )
            _check_rate_limit(resp)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        top_tracks: list[TopTrack] = []
        for item in data.get("items", []):
            artists_display = ", ".join(
                a.get("name", "") for a in item.get("artists", [])
            )
            album_name = item.get("album", {}).get("name", "")
            top_tracks.append(
                TopTrack(
                    external_id=item.get("id", ""),
                    title=item.get("name", ""),
                    artist=artists_display,
                    album=album_name,
                    popularity=item.get("popularity", 0),
                    duration_ms=item.get("duration_ms"),
                    provider="spotify",
                )
            )

        logger.info("Spotify returned %d top track(s)", len(top_tracks))
        return top_tracks

    async def get_top_artists(
        self,
        access_token: str,
        *,
        limit: int = 50,
        time_range: str = "medium_term",
    ) -> list[TopArtist]:
        """Return the user's top artists from Spotify.

        *time_range* must be one of ``"short_term"`` (≈4 weeks),
        ``"medium_term"`` (≈6 months), or ``"long_term"`` (all time).
        """
        logger.debug(
            "Fetching top artists from Spotify (limit=%d, time_range=%s)", limit, time_range
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_SPOTIFY_API_BASE}/me/top/artists",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": min(limit, 50), "time_range": time_range},
            )
            _check_rate_limit(resp)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        top_artists: list[TopArtist] = []
        for item in data.get("items", []):
            top_artists.append(
                TopArtist(
                    external_id=item.get("id", ""),
                    name=item.get("name", ""),
                    genres=item.get("genres", []),
                    popularity=item.get("popularity", 0),
                    provider="spotify",
                )
            )

        logger.info("Spotify returned %d top artist(s)", len(top_artists))
        return top_artists

    async def refresh_token(self, refresh_token: str) -> tuple[str, str, datetime]:
        """Exchange a refresh token for a new access/refresh token pair.

        Returns ``(new_access_token, new_refresh_token, expires_at)``.
        """
        logger.info("Refreshing Spotify access token")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_SPOTIFY_ACCOUNTS_BASE}/api/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.spotify_client_id,
                    "client_secret": settings.spotify_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            token_data: dict[str, Any] = resp.json()

        new_access_token: str = token_data["access_token"]
        # Spotify may or may not return a new refresh token; keep the old one if absent.
        new_refresh_token: str = token_data.get("refresh_token", refresh_token)
        expires_in: int = token_data.get("expires_in", 3600)
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        logger.info("Spotify token refreshed, expires in %ds", expires_in)
        return new_access_token, new_refresh_token, expires_at


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an authorization code for tokens at the Spotify token endpoint."""
    logger.info("Exchanging Spotify authorization code at %s/api/token", _SPOTIFY_ACCOUNTS_BASE)
    logger.debug(
        "Spotify code exchange: redirect_uri=%s, client_id=%s",
        settings.spotify_redirect_uri,
        settings.spotify_client_id,
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_SPOTIFY_ACCOUNTS_BASE}/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        logger.debug(
            "Spotify code exchange response: status=%d", resp.status_code
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
    logger.debug(
        "Spotify authorization code exchange succeeded; response keys: %s",
        list(result.keys()),
    )
    return result


async def fetch_spotify_user(access_token: str) -> dict[str, Any]:
    """Fetch the Spotify user profile for *access_token*."""
    logger.debug("Fetching Spotify user profile from %s/me", _SPOTIFY_API_BASE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_SPOTIFY_API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        logger.debug("Spotify user profile response: status=%d", resp.status_code)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
    logger.info("Spotify user profile fetched — id: %s", result.get("id", "unknown"))
    logger.debug("Spotify user profile keys: %s", list(result.keys()))
    return result
