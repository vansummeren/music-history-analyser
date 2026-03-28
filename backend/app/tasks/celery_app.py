"""Celery application factory."""
from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from app.config import mask_url, settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "music_history_analyser",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis_tasks", "app.tasks.scheduler"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-due-schedules-every-minute": {
            "task": "check_due_schedules",
            "schedule": crontab(),  # every minute
        },
    },
)


@worker_ready.connect  # type: ignore[misc]
def _on_worker_ready(sender: Any, **kwargs: Any) -> None:
    """Log non-sensitive configuration when the Celery worker comes online."""
    sep = "=" * 54
    lines: list[str] = [
        "",
        sep,
        "  Music History Analyser – Celery Worker ready",
        sep,
        f"  Broker              : {mask_url(settings.redis_url)}",
        f"  Result backend      : {mask_url(settings.redis_url)}",
        "  Registered tasks    :",
    ]
    for task_name in sorted(sender.tasks):
        if not task_name.startswith("celery."):
            lines.append(f"    • {task_name}")
    lines.append(sep)
    logger.info("\n".join(lines))
