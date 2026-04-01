"""Celery application factory."""
from __future__ import annotations

import logging
import logging.config
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from app.config import mask_url, settings

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Apply the same timestamped logging format used by the FastAPI app."""
    log_level = settings.log_level.upper()
    fmt = "%(asctime)s %(levelname)-8s %(name)s – %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "timestamped": {
                    "format": fmt,
                    "datefmt": datefmt,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "timestamped",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
    )


_configure_logging()

celery_app = Celery(
    "music_history_analyser",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis_tasks", "app.tasks.scheduler", "app.tasks.history_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "check-due-schedules-every-minute": {
            "task": "check_due_schedules",
            "schedule": crontab(),  # every minute
        },
        "check-due-history-polls-every-minute": {
            "task": "check_due_history_polls",
            "schedule": crontab(),  # every minute — per-account interval enforced in service
        },
    },
)


@worker_ready.connect  # type: ignore
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
    for task_name in sorted(celery_app.tasks):
        if not task_name.startswith("celery."):
            lines.append(f"    • {task_name}")
    lines.append(sep)
    logger.info("\n".join(lines))
