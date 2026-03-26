"""Celery tasks for scheduled analysis runs."""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="run_scheduled_analysis", bind=True, max_retries=3)  # type: ignore
def run_scheduled_analysis(self: object, schedule_id: str) -> dict[str, object]:
    """Execute one analysis run for *schedule_id* and send the result email.

    This is a synchronous Celery task that drives async code via
    ``asyncio.run``.
    """
    return asyncio.run(_run(uuid.UUID(schedule_id)))


async def _run(schedule_id: uuid.UUID) -> dict[str, object]:  # noqa: PLR0911
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models.analysis import Analysis
    from app.models.schedule import Schedule
    from app.services import analysis_service, schedule_service
    from app.services.email_service import send_analysis_result

    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            schedule = await db.get(Schedule, schedule_id)
            if schedule is None:
                logger.warning("Schedule %s not found – skipping", schedule_id)
                return {"status": "skipped", "reason": "schedule not found"}

            if not schedule.is_active:
                logger.info("Schedule %s is inactive – skipping", schedule_id)
                return {"status": "skipped", "reason": "inactive"}

            # Load the related analysis to get its name
            analysis = await db.get(Analysis, schedule.analysis_id)
            if analysis is None:
                logger.warning(
                    "Analysis %s for schedule %s not found – skipping",
                    schedule.analysis_id,
                    schedule_id,
                )
                return {"status": "skipped", "reason": "analysis not found"}

            analysis_name = analysis.name

            # Run the analysis (reuses the existing service logic)
            run = await analysis_service.run_analysis(
                db,
                schedule.analysis_id,
                time_window_days=schedule.time_window_days,
            )

            # Advance the schedule's next_run_at
            await schedule_service.mark_schedule_ran(db, schedule)

            if run.status == "failed":
                logger.error(
                    "Scheduled analysis run %s failed: %s", run.id, run.error
                )
                return {"status": "failed", "run_id": str(run.id), "error": run.error}

            # Send the result email
            try:
                await send_analysis_result(
                    recipient=schedule.recipient_email,
                    schedule_name=f"Schedule {schedule_id}",
                    analysis_name=analysis_name,
                    result_text=run.result_text or "",
                    time_window_days=schedule.time_window_days,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to send email for schedule %s: %s", schedule_id, exc
                )
                # Don't fail the whole task — the analysis ran successfully

            return {"status": "completed", "run_id": str(run.id)}
    finally:
        await engine.dispose()
