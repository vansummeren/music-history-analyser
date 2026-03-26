"""Celery application factory."""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "music_history_analyser",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
