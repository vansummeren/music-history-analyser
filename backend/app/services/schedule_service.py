"""Schedule service — cron helpers and schedule mutation logic."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from croniter import croniter  # type: ignore[import-untyped]  # no stubs available
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

logger = logging.getLogger(__name__)


def compute_next_run(cron: str, after: datetime | None = None) -> datetime:
    """Return the next datetime the cron expression fires after *after*.

    *after* defaults to now (UTC).  The returned datetime is always
    timezone-aware (UTC).
    """
    base = after if after is not None else datetime.now(UTC)
    # croniter works with naive datetimes internally; strip tzinfo for input
    base_naive = base.replace(tzinfo=None)
    itr = croniter(cron, base_naive)
    next_dt: datetime = itr.get_next(datetime)
    return next_dt.replace(tzinfo=UTC)


async def create_schedule(
    db: AsyncSession,
    user_id: uuid.UUID,
    body: ScheduleCreate,
) -> Schedule:
    """Create and persist a new schedule."""
    # Verify the analysis belongs to this user
    analysis = await db.get(Analysis, body.analysis_id)
    if analysis is None or analysis.user_id != user_id:
        raise ValueError("Analysis not found")

    next_run = compute_next_run(body.cron)
    schedule = Schedule(
        user_id=user_id,
        analysis_id=body.analysis_id,
        cron=body.cron,
        time_window_days=body.time_window_days,
        recipient_email=body.recipient_email,
        next_run_at=next_run,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    logger.info(
        "Schedule %s created — analysis: %s, cron: %r, next run: %s",
        schedule.id, body.analysis_id, body.cron, next_run.isoformat(),
    )
    return schedule


async def update_schedule(
    db: AsyncSession,
    schedule: Schedule,
    body: ScheduleUpdate,
) -> Schedule:
    """Apply partial updates to *schedule* and persist."""
    now = datetime.now(UTC)

    if body.cron is not None:
        logger.info(
            "Schedule %s cron updated: %r → %r", schedule.id, schedule.cron, body.cron
        )
        schedule.cron = body.cron
        schedule.next_run_at = compute_next_run(body.cron)
    if body.time_window_days is not None:
        schedule.time_window_days = body.time_window_days
    if body.recipient_email is not None:
        schedule.recipient_email = body.recipient_email
    if body.is_active is not None:
        logger.info(
            "Schedule %s active state changed to %s", schedule.id, body.is_active
        )
        schedule.is_active = body.is_active
        # Re-compute next run when re-activating
        if body.is_active:
            schedule.next_run_at = compute_next_run(schedule.cron)

    schedule.updated_at = now
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def get_due_schedules(db: AsyncSession) -> list[Schedule]:
    """Return all active schedules whose next_run_at is in the past."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(Schedule).where(
            Schedule.is_active.is_(True),
            Schedule.next_run_at <= now,
        )
    )
    due = list(result.scalars().all())
    if due:
        logger.info("Found %d due schedule(s)", len(due))
    return due


async def mark_schedule_ran(db: AsyncSession, schedule: Schedule) -> None:
    """Update last_run_at and advance next_run_at after a successful dispatch."""
    now = datetime.now(UTC)
    schedule.last_run_at = now
    schedule.next_run_at = compute_next_run(schedule.cron, after=now)
    schedule.updated_at = now
    await db.commit()
    logger.info(
        "Schedule %s advanced — next run: %s",
        schedule.id, schedule.next_run_at.isoformat(),
    )
