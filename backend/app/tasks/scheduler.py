"""Celery Beat task — polls the DB every minute for due schedules."""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="check_due_schedules")  # type: ignore
def check_due_schedules() -> dict[str, object]:
    """Find all due schedules and dispatch a ``run_scheduled_analysis`` task for each."""
    return asyncio.run(_check())


async def _check() -> dict[str, object]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.services.schedule_service import get_due_schedules

    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    dispatched: list[str] = []
    try:
        async with SessionLocal() as db:
            due = await get_due_schedules(db)
            for schedule in due:
                celery_app.send_task(
                    "run_scheduled_analysis",
                    args=[str(schedule.id)],
                )
                dispatched.append(str(schedule.id))
                logger.info("Dispatched run_scheduled_analysis for schedule %s", schedule.id)
    finally:
        await engine.dispose()

    return {"dispatched": dispatched}
