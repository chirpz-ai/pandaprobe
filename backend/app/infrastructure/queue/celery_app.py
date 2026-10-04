"""Celery application configuration.

The broker and result backend both point at the Redis instance defined
in settings.  Task modules are auto-discovered from the infrastructure
queue package.
"""

import os
import tempfile
import time
from pathlib import Path

from celery import Celery
from celery.signals import task_postrun, task_prerun, worker_ready

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
    task_ignore_result=True,
    task_track_started=False,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.REDIS_URL,
    task_soft_time_limit=300,
    task_time_limit=360,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_transport_options={
        "socket_keepalive": True,
        "socket_connect_timeout": 10,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },
    redis_socket_keepalive=True,
    redis_retry_on_timeout=True,
    redis_socket_connect_timeout=10,
    redis_backend_health_check_interval=30,
)

celery.conf.beat_schedule = {
    "check-eval-monitors": {
        "task": "check_eval_monitors",
        "schedule": 300.0,
    },
    "dispatch-sync-usage": {
        "task": "dispatch_sync_usage",
        "schedule": 300.0,
    },
    "dispatch-overage-billing": {
        "task": "dispatch_overage_billing",
        "schedule": 21600.0,
    },
    "dispatch-billing-reports": {
        "task": "dispatch_billing_reports",
        "schedule": 300.0,
    },
    "dispatch-hobby-reset": {
        "task": "dispatch_hobby_reset",
        "schedule": 21600.0,
    },
    "expire-stale-invitations": {
        "task": "expire_stale_invitations",
        "schedule": 3600.0,
    },
}

celery.autodiscover_tasks(["app.infrastructure.queue"])


# ---------------------------------------------------------------------------
# Pool liveness heartbeat
#
# ``scripts/worker_health.py`` serves the Cloud Run liveness probe and needs to
# know whether *this container's* pool is still consuming.  Celery's control
# ping cannot answer that: every Cloud Run instance has hostname ``localhost``,
# so all instances share the node name ``celery@localhost`` and a healthy
# sibling happily answers a wedged instance's ping.
#
# So the pool writes its own mtime-based heartbeat to a local file instead.
# A file is inherently instance-local, needs no unique instance id, and costs
# one ``utime`` syscall per task.  These signals fire in the child that runs the
# task, which is exactly the process we need proof of life from.  We stamp both
# *prerun* and *postrun* so a legitimately long task (an eval run may take
# minutes) keeps the heartbeat fresh while it works.
# ---------------------------------------------------------------------------

HEARTBEAT_PATH = Path(os.environ.get("WORKER_HEARTBEAT_PATH", Path(tempfile.gettempdir()) / "pp-worker-heartbeat"))


def _touch_heartbeat() -> None:
    """Record that the pool is alive.  Never raises — this is best-effort."""
    try:
        HEARTBEAT_PATH.touch(exist_ok=True)
        os.utime(HEARTBEAT_PATH, (time.time(), time.time()))
    except OSError:
        pass


@worker_ready.connect
def _heartbeat_on_ready(**_kwargs: object) -> None:
    """Seed the heartbeat so an idle worker is healthy from the moment it boots."""
    _touch_heartbeat()


@task_prerun.connect
def _heartbeat_on_task_start(**_kwargs: object) -> None:
    """Refresh the heartbeat as a task begins, from the child that runs it."""
    _touch_heartbeat()


@task_postrun.connect
def _heartbeat_on_task_end(**_kwargs: object) -> None:
    """Refresh the heartbeat after every task, from the child that ran it."""
    _touch_heartbeat()
