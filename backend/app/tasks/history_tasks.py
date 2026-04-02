"""Celery tasks for polling listening history from streaming accounts."""
from __future__ import annotations

import asyncio
import logging
import uuid

from celery import Task

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="poll_history_for_account", bind=True, max_retries=3)  # type: ignore
def poll_history_for_account(self: Task, account_id: str) -> dict[str, object]:
    """Poll recently-played history for one streaming account and persist results.

    *account_id* is the UUID string of the ``SpotifyAccount`` row.
    If Spotify responds with HTTP 429 the task is automatically retried after
    the number of seconds indicated by the ``Retry-After`` response header.
    """
    from app.services.music.spotify import SpotifyRateLimitError

    try:
        return asyncio.run(_poll(uuid.UUID(account_id)))
    except SpotifyRateLimitError as exc:
        logger.warning(
            "Rate limited by Spotify for account %s; scheduling retry in %ds",
            account_id,
            exc.retry_after,
        )
        raise self.retry(countdown=exc.retry_after, exc=exc) from exc


async def _poll(account_id: uuid.UUID) -> dict[str, object]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.services.history_service import poll_account
    from app.services.music.spotify import SpotifyRateLimitError

    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            new_events = await poll_account(db, account_id)
            return {"status": "completed", "account_id": str(account_id), "new_events": new_events}
    except SpotifyRateLimitError:
        raise  # propagate so the Celery task can schedule a retry
    except Exception as exc:  # noqa: BLE001
        logger.error("History poll failed for account %s: %s", account_id, exc)
        return {"status": "failed", "account_id": str(account_id), "error": str(exc)}
    finally:
        await engine.dispose()


@celery_app.task(name="check_due_history_polls")  # type: ignore
def check_due_history_polls() -> dict[str, object]:
    """Dispatch a ``poll_history_for_account`` task for each account that is due."""
    return asyncio.run(_check())


async def _check() -> dict[str, object]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.services.history_service import get_accounts_due_for_poll

    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    dispatched: list[str] = []
    try:
        async with SessionLocal() as db:
            due = await get_accounts_due_for_poll(db)
            for account in due:
                celery_app.send_task(
                    "poll_history_for_account",
                    args=[str(account.id)],
                )
                dispatched.append(str(account.id))
                logger.info(
                    "Dispatched poll_history_for_account for account %s", account.id
                )
    finally:
        await engine.dispose()

    return {"dispatched": dispatched}
