"""Analysis service — orchestrates history fetch + AI call + result storage."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, AnalysisRun
from app.models.spotify_account import SpotifyAccount
from app.services import crypto
from app.services.ai.base import AIProvider
from app.services.ai.claude import ClaudeAdapter
from app.services.ai.perplexity import PerplexityAdapter
from app.services.music.spotify import SpotifyAdapter

logger = logging.getLogger(__name__)


def _get_ai_adapter(provider: str) -> AIProvider:
    """Return the appropriate AI adapter for *provider*."""
    if provider == "claude":
        return ClaudeAdapter()
    if provider == "perplexity":
        return PerplexityAdapter()
    raise ValueError(f"Unknown AI provider: {provider!r}")


async def run_analysis(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    time_window_days: int = 7,
) -> AnalysisRun:
    """Execute one analysis run and persist the result.

    Fetches the user's top tracks and top artists from Spotify (these are not
    stored in the DB — they are fetched on demand for every analysis run) and
    formats them as a structured text prompt for the configured AI provider.
    The result is stored in an ``AnalysisRun`` row.
    """
    # Load the Analysis with its related objects
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise ValueError(f"Analysis {analysis_id} not found")

    # Load related entities explicitly (lazy="raise" prevents implicit loads)
    from app.models.ai_config import AIConfig

    ai_config = (
        await db.execute(select(AIConfig).where(AIConfig.id == analysis.ai_config_id))
    ).scalar_one()

    spotify_account = (
        await db.execute(
            select(SpotifyAccount).where(
                SpotifyAccount.id == analysis.spotify_account_id
            )
        )
    ).scalar_one()

    # Create a pending run
    run = AnalysisRun(
        analysis_id=analysis.id,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.flush()  # get the run id

    logger.info(
        "Analysis run %s started — analysis: %s, provider: %s, window: %d days",
        run.id, analysis_id, ai_config.provider, time_window_days,
    )

    try:
        # Decrypt the Spotify access token and refresh if expired
        access_token = crypto.decrypt(spotify_account.encrypted_access_token)
        refresh_token = crypto.decrypt(spotify_account.encrypted_refresh_token)

        now = datetime.now(UTC)
        expires_at = spotify_account.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            logger.info(
                "Spotify token expired for account %s — refreshing",
                spotify_account.id,
            )
            music_adapter = SpotifyAdapter()
            access_token, new_refresh, new_expires = await music_adapter.refresh_token(
                refresh_token
            )
            spotify_account.encrypted_access_token = crypto.encrypt(access_token)
            spotify_account.encrypted_refresh_token = crypto.encrypt(new_refresh)
            spotify_account.token_expires_at = new_expires
            spotify_account.updated_at = now
            logger.info(
                "Spotify token refreshed for account %s, new expiry: %s",
                spotify_account.id, new_expires.isoformat(),
            )

        # Verify the account has the scopes required by the top-tracks/artists API.
        # Accounts connected before "user-top-read" was added to SPOTIFY_SCOPES will
        # be missing this scope; the user must re-link their Spotify account to grant it.
        account_scopes = set(spotify_account.scopes.split())
        required_scopes = {"user-top-read"}
        missing_scopes = required_scopes - account_scopes
        if missing_scopes:
            raise ValueError(
                f"Spotify account is missing required scope(s): "
                f"{', '.join(sorted(missing_scopes))}. "
                "Please reconnect your Spotify account to grant the missing permissions."
            )

        # Map time_window_days to a Spotify time_range for top tracks/artists
        # short_term  ≈ 4 weeks  → up to 28 days
        # medium_term ≈ 6 months → up to ~180 days
        # long_term   = all time → anything longer
        if time_window_days <= 28:
            time_range = "short_term"
        elif time_window_days <= 180:
            time_range = "medium_term"
        else:
            time_range = "long_term"

        music_adapter = SpotifyAdapter()

        # Fetch top tracks (not stored in DB; used only for this analysis run)
        top_tracks = await music_adapter.get_top_tracks(
            access_token, limit=50, time_range=time_range
        )
        logger.info(
            "Fetched %d top track(s) for analysis %s (time_range: %s)",
            len(top_tracks), analysis_id, time_range,
        )

        # Fetch top artists (not stored in DB; used only for this analysis run)
        top_artists = await music_adapter.get_top_artists(
            access_token, limit=50, time_range=time_range
        )
        logger.info(
            "Fetched %d top artist(s) for analysis %s (time_range: %s)",
            len(top_artists), analysis_id, time_range,
        )

        # Format top tracks as plain text
        if top_tracks:
            track_lines = [
                f"{i + 1}. {t.title} — {t.artist} ({t.album})"
                for i, t in enumerate(top_tracks)
            ]
            track_list = "Top Tracks:\n" + "\n".join(track_lines)
        else:
            track_list = "Top Tracks:\n(no top tracks found)"

        # Format top artists as plain text
        if top_artists:
            artist_lines = [
                f"{i + 1}. {a.name}" + (f" [{', '.join(a.genres[:3])}]" if a.genres else "")
                for i, a in enumerate(top_artists)
            ]
            artist_list = "Top Artists:\n" + "\n".join(artist_lines)
        else:
            artist_list = "Top Artists:\n(no top artists found)"

        # Combine into the track_list string passed to the AI adapter
        combined_list = f"{track_list}\n\n{artist_list}"

        # Decrypt the AI API key and call the AI provider
        api_key = crypto.decrypt(ai_config.encrypted_api_key)
        ai_adapter = _get_ai_adapter(ai_config.provider)
        logger.info(
            "Calling AI provider %r for analysis run %s",
            ai_config.provider, run.id,
        )
        ai_result = await ai_adapter.analyse(
            api_key=api_key,
            prompt=analysis.prompt,
            track_list=combined_list,
        )

        # Update run with success
        run.status = "completed"
        run.result_text = ai_result.text
        run.model = ai_result.model
        run.input_tokens = ai_result.input_tokens
        run.output_tokens = ai_result.output_tokens
        run.completed_at = datetime.now(UTC)
        logger.info(
            "Analysis run %s completed — model: %s, tokens: %d in / %d out",
            run.id, ai_result.model, ai_result.input_tokens, ai_result.output_tokens,
        )

    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(UTC)
        logger.error("Analysis run %s failed: %s", run.id, exc)

    await db.commit()
    await db.refresh(run)
    return run
