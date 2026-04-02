"""Celery application configuration.

The broker and result backend both point at the Redis instance defined
in settings.  Task modules are auto-discovered from the infrastructure
queue package.
"""

from celery import Celery
from celery.schedules import crontab

from app.registry.settings import settings

celery = Celery(
    "pandaprobe",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.REDIS_URL,
)

celery.conf.beat_schedule = {
    "check-eval-monitors": {
        "task": "check_eval_monitors",
        "schedule": 300.0,
    },
    "sync-usage-to-db": {
        "task": "sync_usage_to_db",
        "schedule": 300.0,
    },
    "process-overage-billing": {
        "task": "process_overage_billing",
        "schedule": crontab(hour=0, minute=0),
    },
    "reset-hobby-periods": {
        "task": "reset_hobby_periods",
        "schedule": 21600.0,
    },
}

celery.autodiscover_tasks(["app.infrastructure.queue"])
