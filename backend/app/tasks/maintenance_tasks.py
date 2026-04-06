"""Celery maintenance tasks — housekeeping jobs that run on a schedule."""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="cleanup_old_logs")  # type: ignore
def cleanup_old_logs() -> dict[str, object]:
    """Delete ``app_logs`` rows older than ``settings.log_retention_days``."""
    return asyncio.run(_cleanup())


async def _cleanup() -> dict[str, object]:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models.app_log import AppLog

    cutoff = datetime.now(UTC) - timedelta(days=settings.log_retention_days)
    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                delete(AppLog).where(AppLog.created_at < cutoff)
            )
            await db.commit()
            deleted: int = result.rowcount
    finally:
        await engine.dispose()

    logger.info(
        "cleanup_old_logs: deleted %d log row(s) older than %d day(s)",
        deleted,
        settings.log_retention_days,
    )
    return {"deleted": deleted, "retention_days": settings.log_retention_days}
