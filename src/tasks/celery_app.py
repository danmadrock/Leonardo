from __future__ import annotations
from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "leonardo",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.research_task"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

__all__ = ["celery_app"]