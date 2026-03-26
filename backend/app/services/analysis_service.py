"""Analysis service — orchestrates history fetch + AI call + result storage."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, AnalysisRun
from app.models.spotify_account import SpotifyAccount
from app.services import crypto
from app.services.ai.base import AIProvider
from app.services.ai.claude import ClaudeAdapter
from app.services.ai.perplexity import PerplexityAdapter
from app.services.music.spotify import SpotifyAdapter


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

    Fetches recent Spotify history, formats a track list, calls the configured
    AI provider, and stores the result in an ``AnalysisRun`` row.
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

    try:
        # Decrypt the Spotify access token and refresh if expired
        access_token = crypto.decrypt(spotify_account.encrypted_access_token)
        refresh_token = crypto.decrypt(spotify_account.encrypted_refresh_token)

        now = datetime.now(UTC)
        expires_at = spotify_account.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            music_adapter = SpotifyAdapter()
            access_token, new_refresh, new_expires = await music_adapter.refresh_token(
                refresh_token
            )
            spotify_account.encrypted_access_token = crypto.encrypt(access_token)
            spotify_account.encrypted_refresh_token = crypto.encrypt(new_refresh)
            spotify_account.token_expires_at = new_expires
            spotify_account.updated_at = now

        # Fetch history for the specified time window
        music_adapter = SpotifyAdapter()
        after = now - timedelta(days=time_window_days)
        tracks = await music_adapter.get_recently_played(
            access_token, after=after, limit=50
        )

        # Format track list as plain text
        if tracks:
            track_lines = [
                f"{i + 1}. {t.title} — {t.artist} ({t.album})"
                f" [{t.played_at.strftime('%Y-%m-%d %H:%M')}]"
                for i, t in enumerate(tracks)
            ]
            track_list = "\n".join(track_lines)
        else:
            track_list = "(no tracks found in the last 7 days)"

        # Decrypt the AI API key and call the AI provider
        api_key = crypto.decrypt(ai_config.encrypted_api_key)
        ai_adapter = _get_ai_adapter(ai_config.provider)
        ai_result = await ai_adapter.analyse(
            api_key=api_key,
            prompt=analysis.prompt,
            track_list=track_list,
        )

        # Update run with success
        run.status = "completed"
        run.result_text = ai_result.text
        run.model = ai_result.model
        run.input_tokens = ai_result.input_tokens
        run.output_tokens = ai_result.output_tokens
        run.completed_at = datetime.now(UTC)

    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(run)
    return run
