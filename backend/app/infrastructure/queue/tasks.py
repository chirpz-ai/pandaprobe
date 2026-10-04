"""Celery task definitions for background processing.

Each task runs inside the worker process.  Because Celery workers are
synchronous by default, we use ``asyncio.run()`` to bridge into the
async SQLAlchemy session.

Two task families:
- **process_trace** -- persist an ingested trace to PostgreSQL.
- **execute_eval_run** -- run metrics against a batch of traces and
  persist trace scores.

**Why NullPool?**  Each ``asyncio.run()`` call creates a new event loop.
A pooled engine holds connections bound to the previous loop, causing
``"attached to a different loop"`` errors on the next task.  ``NullPool``
creates a fresh connection per session and discards it immediately,
avoiding cross-loop contamination.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.queue.celery_app import celery
from app.logging import logger
from app.registry.exceptions import QuotaExceededError
from app.registry.settings import settings

_worker_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
_worker_session_factory = async_sessionmaker(
    bind=_worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def _worker_session() -> AsyncGenerator:
    """Yield an async session safe for Celery workers.

    Uses a module-level ``NullPool`` engine — safe across event loops
    because NullPool holds zero idle connections.  Each session opens
    a fresh TCP connection and closes it on exit.
    """
    async with _worker_session_factory() as session:
        yield session


#: How long a dispatcher holds its single-flight lock. Longer than any dispatch
#: takes (~3s for ~500 orgs) but short enough that a killed worker cannot block
#: the next scheduled cycle, which is 300s away for the usage/monitor schedules.
_DISPATCH_LOCK_TTL = 120
_DISPATCH_LOCK_PREFIX = "pp:dispatch-lock:"


@asynccontextmanager
async def _dispatch_once(name: str) -> AsyncGenerator[bool, None]:
    """Yield True only for the first caller to claim ``name`` within the TTL.

    Dispatchers fan out one task per organisation, so every duplicate dispatch
    multiplies the queue by the org count. The observed case is recovery from a
    worker outage: beat keeps queueing on its 300s schedule regardless, so a
    6.6h wedge left 79 dispatch messages that all ran within two minutes of the
    restart and fanned out ~3,000 usage-sync tasks against ~460 real orgs. This
    collapses that thundering herd into one fan-out per TTL.

    Fails OPEN — if Redis is unreachable we still dispatch, because dropping
    usage sync silently is worse than dispatching twice. (Largely academic: the
    lock shares Redis with the broker, so a dispatcher that cannot reach Redis
    could not have received this task nor enqueued its children anyway.)
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        claimed = bool(await client.set(f"{_DISPATCH_LOCK_PREFIX}{name}", "1", nx=True, ex=_DISPATCH_LOCK_TTL))
    except Exception as exc:  # noqa: BLE001 - never let the lock itself break dispatch
        logger.warning("dispatch_lock_unavailable", dispatcher=name, error=str(exc))
        claimed = True
    try:
        yield claimed
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Trace persistence
# ---------------------------------------------------------------------------


@celery.task(name="process_trace", bind=True, max_retries=3, default_retry_delay=5)
def process_trace(self: Any, payload: dict[str, Any]) -> dict[str, str]:
    """Deserialise a trace payload and persist it to PostgreSQL.

    Args:
        self: Celery task instance (injected by ``bind=True``).
        payload: JSON-serialisable dict produced by ``Trace.model_dump(mode='json')``.

    Returns:
        A dict with ``trace_id`` and ``status`` for result inspection.
    """
    try:
        return asyncio.run(_persist_trace(payload))
    except SoftTimeLimitExceeded:
        # Retrying a timeout just burns the limit again (max_retries + 1 times).
        logger.error("process_trace_timeout", trace_id=payload.get("trace_id"))
        raise
    except Exception as exc:
        logger.error("process_trace_failed", error=str(exc), trace_id=payload.get("trace_id"))
        raise self.retry(exc=exc)


async def _persist_trace(payload: dict[str, Any]) -> dict[str, str]:
    """Async helper that opens a DB session and saves the trace."""
    from app.core.traces.entities import Trace
    from app.infrastructure.db.repositories.trace_repo import TraceRepository

    trace = Trace.model_validate(payload)

    async with _worker_session() as session:
        repo = TraceRepository(session)
        await repo.upsert_trace(trace)
        await session.commit()

    logger.info("trace_persisted", trace_id=str(trace.trace_id))
    return {"trace_id": str(trace.trace_id), "status": "persisted"}


# ---------------------------------------------------------------------------
# Eval run execution
# ---------------------------------------------------------------------------


_EVAL_SOFT_TIME_LIMIT = 3300  # 55 min
_EVAL_TIME_LIMIT = 3600  # 60 min


@celery.task(
    name="execute_eval_run",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=_EVAL_SOFT_TIME_LIMIT,
    time_limit=_EVAL_TIME_LIMIT,
)
def execute_eval_run(
    self: Any,
    run_id: str,
    project_id: str,
    trace_ids: list[str],
    trace_metric_map: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Run requested metrics against a batch of traces.

    The eval run row must already exist in the database (created by
    the API handler).  This task transitions it through
    PENDING -> RUNNING -> COMPLETED/FAILED.

    Args:
        self: Celery task instance.
        run_id: UUID of the eval run.
        project_id: UUID of the owning project.
        trace_ids: List of trace UUID strings to evaluate.
        trace_metric_map: Optional per-trace metric override. When set,
            each trace only runs the metrics listed for it instead of
            all metrics from the run. Used by retry to avoid Cartesian
            product re-evaluation.

    Returns:
        A dict summarising the eval run outcome.
    """
    try:
        return asyncio.run(_run_eval_run(run_id, project_id, trace_ids, trace_metric_map))
    except SoftTimeLimitExceeded:
        logger.error("execute_eval_run_timeout", run_id=run_id)
        asyncio.run(_fail_eval_run(run_id, "Eval run exceeded its time limit."))
        raise
    except Exception as exc:
        logger.error("execute_eval_run_failed", error=str(exc), run_id=run_id)
        asyncio.run(_fail_eval_run(run_id, str(exc)))
        raise self.retry(exc=exc)


async def _run_eval_run(
    run_id: str,
    project_id: str,
    trace_ids: list[str],
    trace_metric_map: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Core async logic for executing an eval run."""
    from datetime import datetime, timezone
    from uuid import UUID, uuid4

    from app.core.evals.entities import TraceScore
    from app.core.evals.metrics import get_metric
    from app.core.evals.metrics.base import MetricResult
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.infrastructure.db.repositories.trace_repo import TraceRepository
    from app.infrastructure.llm.engine import LLMEngine
    from app.registry.constants import EvaluationStatus, ScoreDataType, ScoreSource, ScoreStatus

    run_uuid = UUID(run_id)
    proj_uuid = UUID(project_id)

    llm = LLMEngine()

    async with _worker_session() as session:
        eval_repo = EvalRepository(session)
        trace_repo = TraceRepository(session)

        await eval_repo.delete_scores_for_run(run_uuid, proj_uuid)
        await eval_repo.reset_run_counters(run_uuid)
        await eval_repo.update_run_status(run_uuid, EvaluationStatus.RUNNING)
        await session.commit()

        run = await eval_repo.get_eval_run(run_uuid, proj_uuid)
        if run is None:
            raise ValueError(f"Eval run {run_id} not found")

        for tid_str in trace_ids:
            tid = UUID(tid_str)
            trace = await trace_repo.get_trace(tid, proj_uuid)
            if trace is None:
                logger.warning("eval_run_trace_not_found", run_id=run_id, trace_id=tid_str)
                await eval_repo.increment_progress(run_uuid)
                await session.commit()
                continue

            metrics_for_trace = (
                trace_metric_map.get(tid_str, run.metric_names) if trace_metric_map else run.metric_names
            )
            for metric_name in metrics_for_trace:
                metric_cls = get_metric(metric_name)
                metric = metric_cls()

                now = datetime.now(timezone.utc)
                try:
                    result: MetricResult = await metric.evaluate(trace, llm, model=run.model)

                    score = TraceScore(
                        id=uuid4(),
                        trace_id=tid,
                        project_id=proj_uuid,
                        name=metric_name,
                        data_type=ScoreDataType.NUMERIC,
                        value=str(round(result.score, 4)),
                        source=ScoreSource.AUTOMATED,
                        status=ScoreStatus.SUCCESS,
                        eval_run_id=run_uuid,
                        reason=result.reason,
                        environment=trace.environment,
                        metadata=result.metadata,
                        created_at=now,
                        updated_at=now,
                    )
                    await eval_repo.create_score(score)

                    logger.info(
                        "metric_completed",
                        run_id=run_id,
                        trace_id=tid_str,
                        metric=metric_name,
                        score=result.score,
                    )
                except Exception as exc:
                    logger.error(
                        "metric_failed",
                        run_id=run_id,
                        trace_id=tid_str,
                        metric=metric_name,
                        error=str(exc),
                    )
                    failed_score = TraceScore(
                        id=uuid4(),
                        trace_id=tid,
                        project_id=proj_uuid,
                        name=metric_name,
                        data_type=ScoreDataType.NUMERIC,
                        value=None,
                        source=ScoreSource.AUTOMATED,
                        status=ScoreStatus.FAILED,
                        eval_run_id=run_uuid,
                        reason=f"Metric execution failed: {exc}",
                        environment=trace.environment,
                        metadata={},
                        created_at=now,
                        updated_at=now,
                    )
                    await eval_repo.create_score(failed_score)
                    await eval_repo.increment_failed(run_uuid)

            await eval_repo.increment_progress(run_uuid)
            await session.commit()

        await eval_repo.update_run_status(run_uuid, EvaluationStatus.COMPLETED)
        await session.commit()

    logger.info("eval_run_completed", run_id=run_id)
    return {"run_id": run_id, "status": "completed"}


async def _fail_eval_run(run_id: str, error_message: str) -> None:
    """Mark an eval run as FAILED on unrecoverable errors."""
    from uuid import UUID

    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.registry.constants import EvaluationStatus

    try:
        async with _worker_session() as session:
            repo = EvalRepository(session)
            await repo.update_run_status(UUID(run_id), EvaluationStatus.FAILED, error_message=error_message)
            await session.commit()
    except Exception:
        logger.error("fail_eval_run_update_failed", run_id=run_id)


# ---------------------------------------------------------------------------
# Eval monitor tick
# ---------------------------------------------------------------------------


@celery.task(name="check_eval_monitors", bind=True, max_retries=0)
def check_eval_monitors(self: Any) -> dict[str, Any]:
    """Periodic tick: query due monitors and fan out into per-monitor sub-tasks.

    This is a lightweight dispatcher. It acquires a Redis lock, queries
    for due monitors, then fires one ``process_single_monitor`` task per
    monitor into the Celery queue for parallel execution across workers.
    """
    try:
        return asyncio.run(_check_eval_monitors())
    except Exception as exc:
        logger.error("check_eval_monitors_failed", error=str(exc))
        return {"error": str(exc)}


async def _check_eval_monitors() -> dict[str, Any]:
    from datetime import datetime, timezone

    from app.core.evals.cadence import compute_next_run
    from app.infrastructure.db.repositories.eval_repo import EvalRepository

    import redis

    redis_client = redis.from_url(settings.REDIS_URL)
    try:
        lock = redis_client.lock("check_eval_monitors", timeout=60)
        if not lock.acquire(blocking=False):
            logger.info("check_eval_monitors_skipped", reason="lock held by another worker")
            return {"status": "skipped", "reason": "lock"}

        monitors_to_dispatch: list[tuple[str, str]] = []
        try:
            now = datetime.now(timezone.utc)

            async with _worker_session() as session:
                eval_repo = EvalRepository(session)
                due_monitors = await eval_repo.get_due_monitors(now)

                for monitor in due_monitors:
                    next_run = compute_next_run(monitor.cadence, now)
                    await eval_repo.reschedule_monitor(
                        monitor.id,
                        next_run_at=next_run,
                    )
                    monitors_to_dispatch.append((str(monitor.id), str(monitor.project_id)))

                await session.commit()

        finally:
            try:
                lock.release()
            except Exception:
                pass
    finally:
        redis_client.close()

    for monitor_id, project_id in monitors_to_dispatch:
        process_single_monitor.delay(monitor_id, project_id)

    dispatched = len(monitors_to_dispatch)
    summary = {"status": "completed", "dispatched": dispatched}
    logger.info("check_eval_monitors_done", **summary)
    return summary


@celery.task(name="process_single_monitor", bind=True, max_retries=2, default_retry_delay=30)
def process_single_monitor(self: Any, monitor_id: str, project_id: str) -> dict[str, str]:
    """Process a single due monitor: check for new data, spawn an eval run if needed.

    Runs as an independent task so multiple monitors execute in parallel
    across all available worker slots.
    """
    try:
        return asyncio.run(_process_single_monitor(monitor_id, project_id))
    except QuotaExceededError:
        logger.warning(
            "process_single_monitor_quota_exceeded",
            monitor_id=monitor_id,
        )
        return {"monitor_id": monitor_id, "status": "quota_exceeded"}
    except SoftTimeLimitExceeded:
        logger.error("process_single_monitor_timeout", monitor_id=monitor_id)
        raise
    except Exception as exc:
        logger.error("process_single_monitor_failed", monitor_id=monitor_id, error=str(exc))
        raise self.retry(exc=exc)


async def _process_single_monitor(monitor_id: str, project_id: str) -> dict[str, str]:
    from datetime import datetime, timezone
    from uuid import UUID

    import redis.asyncio as aioredis

    from app.infrastructure.db.models import ProjectModel
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.registry.constants import UsageCategory
    from app.services.eval_service import EvalService
    from app.services.usage_service import UsageService

    mid = UUID(monitor_id)
    pid = UUID(project_id)

    async with _worker_session() as session:
        eval_repo = EvalRepository(session)
        svc = EvalService(session)

        monitor = await eval_repo.get_monitor(mid, pid)
        if monitor is None:
            logger.warning("process_single_monitor_not_found", monitor_id=monitor_id)
            return {"monitor_id": monitor_id, "status": "not_found"}

        if await svc.should_skip_monitor(monitor):
            logger.info("monitor_skipped_no_changes", monitor_id=monitor_id)
            return {"monitor_id": monitor_id, "status": "skipped"}

        project = await session.get(ProjectModel, pid)
        if project is None:
            logger.error("process_single_monitor_project_missing", monitor_id=monitor_id, project_id=project_id)
            return {"monitor_id": monitor_id, "status": "project_missing"}

        run, target_ids = await svc._spawn_run_for_monitor(monitor)

        category = UsageCategory.TRACE_EVALS if monitor.target_type == "TRACE" else UsageCategory.SESSION_EVALS
        billable_units = run.total_targets * len(run.metric_names)
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            usage_svc = UsageService(redis_client, session)
            await usage_svc.check_and_increment(project.org_id, category, count=billable_units)
            try:
                now = datetime.now(timezone.utc)
                await eval_repo.advance_monitor(
                    mid,
                    last_run_at=now,
                    last_run_id=run.id,
                )
                await session.commit()
            except Exception:
                await usage_svc.rollback_increment(project.org_id, category, count=billable_units)
                raise
        finally:
            await redis_client.aclose()

        svc._dispatch_monitor_run(monitor.target_type, run.id, monitor.project_id, target_ids)

        logger.info(
            "monitor_run_spawned",
            monitor_id=monitor_id,
            run_id=str(run.id),
            billable_units=billable_units,
        )
        return {"monitor_id": monitor_id, "status": "spawned", "run_id": str(run.id)}


# ---------------------------------------------------------------------------
# Session eval run execution
# ---------------------------------------------------------------------------

SIGNAL_METRICS = ["confidence", "coherence", "loop_detection", "tool_correctness"]


@celery.task(
    name="execute_session_eval_run",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=_EVAL_SOFT_TIME_LIMIT,
    time_limit=_EVAL_TIME_LIMIT,
)
def execute_session_eval_run(
    self: Any,
    run_id: str,
    project_id: str,
    session_ids: list[str],
) -> dict[str, str]:
    """Run session-level metrics across one or more sessions.

    Fully self-contained: resolves traces per session, computes all
    trace-level signals (persisting each as a TraceScore), then passes
    the precomputed signals to session metrics for pure aggregation.
    """
    try:
        return asyncio.run(_run_session_eval(run_id, project_id, session_ids))
    except SoftTimeLimitExceeded:
        logger.error("execute_session_eval_run_timeout", run_id=run_id)
        asyncio.run(_fail_eval_run(run_id, "Session eval run exceeded its time limit."))
        raise
    except Exception as exc:
        logger.error("execute_session_eval_run_failed", error=str(exc), run_id=run_id)
        asyncio.run(_fail_eval_run(run_id, str(exc)))
        raise self.retry(exc=exc)


async def _run_session_eval(
    run_id: str,
    project_id: str,
    session_ids: list[str],
) -> dict[str, str]:
    """Core async logic for executing a session eval run."""
    from datetime import datetime, timezone
    from uuid import UUID, uuid4

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.evals.entities import SessionScore, TraceScore
    from app.core.evals.metrics import get_metric, get_session_metric
    from app.core.evals.metrics.base import MetricResult
    from app.core.evals.metrics.utils import to_text
    from app.core.traces.entities import Span, Trace
    from app.infrastructure.db.models import SpanModel, TraceModel
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.infrastructure.llm.engine import LLMEngine
    from app.registry.constants import (
        EvaluationStatus,
        ScoreDataType,
        ScoreSource,
        ScoreStatus,
        SpanKind,
        SpanStatusCode,
        TraceStatus,
    )

    run_uuid = UUID(run_id)
    proj_uuid = UUID(project_id)

    llm = LLMEngine()

    async with _worker_session() as session:
        eval_repo = EvalRepository(session)

        # Phase 0 -- Setup
        await eval_repo.delete_session_scores_for_run(run_uuid, proj_uuid)
        await eval_repo.delete_scores_for_run(run_uuid, proj_uuid)
        await eval_repo.reset_run_counters(run_uuid)
        await eval_repo.update_run_status(run_uuid, EvaluationStatus.RUNNING)
        await session.commit()

        run = await eval_repo.get_eval_run(run_uuid, proj_uuid)
        if run is None:
            raise ValueError(f"Eval run {run_id} not found")

        signal_weights = run.filters.get("signal_weights")

        # Phase 1 -- Per-session processing
        for sid in session_ids:
            # Step A -- Resolve traces
            stmt = (
                select(TraceModel)
                .options(selectinload(TraceModel.spans))
                .where(TraceModel.project_id == proj_uuid, TraceModel.session_id == sid)
                .order_by(TraceModel.started_at.asc())
            )
            result = await session.execute(stmt)
            trace_rows = result.scalars().all()

            if not trace_rows:
                logger.warning("session_eval_no_traces", run_id=run_id, session_id=sid)
                await eval_repo.increment_progress(run_uuid)
                await session.commit()
                continue

            traces: list[Trace] = []
            for row in trace_rows:
                spans = [
                    Span(
                        span_id=s.span_id,
                        trace_id=s.trace_id,
                        parent_span_id=s.parent_span_id,
                        name=s.name,
                        kind=SpanKind(s.kind),
                        status=SpanStatusCode(s.status),
                        input=s.input,
                        output=s.output,
                        model=s.model,
                        token_usage=s.token_usage,
                        metadata=s.metadata_,
                        started_at=s.started_at,
                        ended_at=s.ended_at,
                        error=s.error,
                        completion_start_time=s.completion_start_time,
                        model_parameters=s.model_parameters,
                        cost=s.cost,
                    )
                    for s in row.spans
                ]
                traces.append(
                    Trace(
                        trace_id=row.trace_id,
                        project_id=row.project_id,
                        name=row.name,
                        status=TraceStatus(row.status),
                        input=row.input,
                        output=row.output,
                        metadata=row.metadata_,
                        started_at=row.started_at,
                        ended_at=row.ended_at,
                        session_id=row.session_id,
                        user_id=row.user_id,
                        tags=row.tags or [],
                        environment=row.environment,
                        release=row.release,
                        spans=spans,
                    )
                )

            # Step B -- Warm embedding cache
            all_texts = []
            for t in traces:
                inp = to_text(t.input)
                out = to_text(t.output)
                if inp:
                    all_texts.append(inp)
                if out:
                    all_texts.append(out)
            if all_texts:
                try:
                    await llm.embed_texts(all_texts)
                except Exception as exc:
                    logger.warning("session_eval_embed_warmup_failed", error=str(exc))

            # Step C -- Compute and persist trace-level signals
            precomputed_signals: dict[str, dict[str, float]] = {}

            for i, trace_entity in enumerate(traces):
                tid = trace_entity.trace_id
                trace_signals: dict[str, float] = {}

                for signal_name in SIGNAL_METRICS:
                    existing = await eval_repo.find_existing_trace_score(tid, signal_name)

                    if existing and existing.value is not None:
                        score_value = float(existing.value)
                        logger.debug(
                            "signal_reused",
                            run_id=run_id,
                            trace_id=str(tid),
                            signal=signal_name,
                            score=score_value,
                        )
                    else:
                        try:
                            metric_cls = get_metric(signal_name)
                            metric_instance = metric_cls()
                            result: MetricResult = await metric_instance.evaluate(
                                trace_entity,
                                llm,
                                model=run.model,
                                session_traces=traces[:i],
                            )
                            score_value = result.score

                            now = datetime.now(timezone.utc)
                            trace_score = TraceScore(
                                id=uuid4(),
                                trace_id=tid,
                                project_id=proj_uuid,
                                name=signal_name,
                                data_type=ScoreDataType.NUMERIC,
                                value=str(round(score_value, 4)),
                                source=ScoreSource.AUTOMATED,
                                status=ScoreStatus.SUCCESS,
                                eval_run_id=run_uuid,
                                reason=result.reason,
                                environment=trace_entity.environment,
                                metadata=result.metadata or {},
                                created_at=now,
                                updated_at=now,
                            )
                            await eval_repo.create_score(trace_score)

                            logger.info(
                                "signal_computed",
                                run_id=run_id,
                                trace_id=str(tid),
                                signal=signal_name,
                                score=score_value,
                            )
                        except Exception as exc:
                            logger.error(
                                "signal_failed",
                                run_id=run_id,
                                trace_id=str(tid),
                                signal=signal_name,
                                error=str(exc),
                            )
                            score_value = None

                            now = datetime.now(timezone.utc)
                            failed_score = TraceScore(
                                id=uuid4(),
                                trace_id=tid,
                                project_id=proj_uuid,
                                name=signal_name,
                                data_type=ScoreDataType.NUMERIC,
                                value=None,
                                source=ScoreSource.AUTOMATED,
                                status=ScoreStatus.FAILED,
                                eval_run_id=run_uuid,
                                reason=f"Signal computation failed: {exc}",
                                environment=trace_entity.environment,
                                metadata={},
                                created_at=now,
                                updated_at=now,
                            )
                            await eval_repo.create_score(failed_score)

                    if score_value is not None:
                        trace_signals[signal_name] = score_value

                precomputed_signals[str(tid)] = trace_signals

            await session.commit()

            # Step D -- Run session metrics (pure aggregation)
            for metric_name in run.metric_names:
                now = datetime.now(timezone.utc)
                try:
                    session_metric_cls = get_session_metric(metric_name)
                    session_metric = session_metric_cls()

                    result = await session_metric.evaluate(
                        session_id=sid,
                        traces=traces,
                        llm=llm,
                        model=run.model,
                        signal_weights=signal_weights,
                        precomputed_signals=precomputed_signals,
                    )

                    score_entity = SessionScore(
                        id=uuid4(),
                        session_id=sid,
                        project_id=proj_uuid,
                        name=metric_name,
                        data_type=ScoreDataType.NUMERIC,
                        value=str(round(result.score, 4)),
                        source=ScoreSource.AUTOMATED,
                        status=ScoreStatus.SUCCESS,
                        eval_run_id=run_uuid,
                        reason=result.reason,
                        metadata=result.metadata or {},
                        created_at=now,
                        updated_at=now,
                    )
                    await eval_repo.create_session_score(score_entity)

                    logger.info(
                        "session_metric_completed",
                        run_id=run_id,
                        session_id=sid,
                        metric=metric_name,
                        score=result.score,
                    )
                except Exception as exc:
                    logger.error(
                        "session_metric_failed",
                        run_id=run_id,
                        session_id=sid,
                        metric=metric_name,
                        error=str(exc),
                    )
                    failed_entity = SessionScore(
                        id=uuid4(),
                        session_id=sid,
                        project_id=proj_uuid,
                        name=metric_name,
                        data_type=ScoreDataType.NUMERIC,
                        value=None,
                        source=ScoreSource.AUTOMATED,
                        status=ScoreStatus.FAILED,
                        eval_run_id=run_uuid,
                        reason=f"Session metric failed: {exc}",
                        metadata={},
                        created_at=now,
                        updated_at=now,
                    )
                    await eval_repo.create_session_score(failed_entity)
                    await eval_repo.increment_failed(run_uuid)

            # Step E -- Progress
            await eval_repo.increment_progress(run_uuid)
            await session.commit()

        # Phase 2 -- Finalize
        await eval_repo.update_run_status(run_uuid, EvaluationStatus.COMPLETED)
        await session.commit()

    logger.info("session_eval_run_completed", run_id=run_id)
    return {"run_id": run_id, "status": "completed"}


# ---------------------------------------------------------------------------
# Usage sync & billing tasks  (dispatcher + per-org worker pattern)
#
# Each beat task is a lightweight *dispatcher* that queries eligible org
# IDs, then fans out one Celery sub-task per org.  The sub-tasks run in
# parallel across all available workers, each with its own DB session
# and transaction, so one failure is isolated to a single org.
# ---------------------------------------------------------------------------


# -- Usage sync ---------------------------------------------------------------


@celery.task(name="dispatch_sync_usage", bind=True, max_retries=0)
def dispatch_sync_usage(self: Any) -> dict[str, Any]:
    """Dispatcher: query all active org IDs and fan out sync tasks."""
    try:
        return asyncio.run(_dispatch_sync_usage())
    except Exception as exc:
        logger.error("dispatch_sync_usage_failed", error=str(exc))
        return {"error": str(exc)}


async def _dispatch_sync_usage() -> dict[str, Any]:
    from app.infrastructure.db.repositories.billing_repo import BillingRepository

    async with _dispatch_once("sync_usage") as claimed:
        if not claimed:
            logger.info("dispatch_sync_usage_skipped_duplicate")
            return {"status": "skipped_duplicate", "count": 0}

        async with _worker_session() as session:
            org_ids = await BillingRepository(session).list_all_active_org_ids()

        for oid in org_ids:
            sync_single_org_usage.delay(str(oid))

    logger.info("dispatch_sync_usage_done", dispatched=len(org_ids))
    return {"status": "dispatched", "count": len(org_ids)}


@celery.task(name="sync_single_org_usage", bind=True, max_retries=2, default_retry_delay=10)
def sync_single_org_usage(self: Any, org_id_str: str) -> dict[str, str]:
    """Worker: sync Redis counters to PostgreSQL for a single org."""
    try:
        return asyncio.run(_sync_single_org_usage(org_id_str))
    except Exception as exc:
        logger.error("sync_single_org_usage_failed", org_id=org_id_str, error=str(exc))
        raise self.retry(exc=exc)


async def _sync_single_org_usage(org_id_str: str) -> dict[str, str]:
    from uuid import UUID

    import redis.asyncio as aioredis

    from app.services.usage_service import UsageService

    org_id = UUID(org_id_str)
    async with _worker_session() as session:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            usage_svc = UsageService(redis_client, session)
            await usage_svc.sync_to_database(org_id)
            await session.commit()
        finally:
            await redis_client.aclose()

    return {"org_id": org_id_str, "status": "synced"}


# -- Overage billing ----------------------------------------------------------


@celery.task(name="dispatch_overage_billing", bind=True, max_retries=0)
def dispatch_overage_billing(self: Any) -> dict[str, Any]:
    """Dispatcher: query paid org IDs and fan out billing tasks."""
    try:
        return asyncio.run(_dispatch_overage_billing())
    except Exception as exc:
        logger.error("dispatch_overage_billing_failed", error=str(exc))
        return {"error": str(exc)}


async def _dispatch_overage_billing() -> dict[str, Any]:
    from app.infrastructure.db.repositories.billing_repo import BillingRepository

    async with _dispatch_once("overage_billing") as claimed:
        if not claimed:
            logger.info("dispatch_overage_billing_skipped_duplicate")
            return {"status": "skipped_duplicate", "count": 0}

        async with _worker_session() as session:
            org_ids = await BillingRepository(session).list_paid_active_org_ids()

        for oid in org_ids:
            bill_single_org.delay(str(oid))

    logger.info("dispatch_overage_billing_done", dispatched=len(org_ids))
    return {"status": "dispatched", "count": len(org_ids)}


@celery.task(name="dispatch_billing_reports")
def dispatch_billing_reports() -> dict[str, int]:
    """Recover durable intents and check recently closed periods for late counters."""
    return asyncio.run(_dispatch_billing_reports())


async def _dispatch_billing_reports() -> dict[str, int]:
    from datetime import datetime, timedelta, timezone

    from app.infrastructure.db.repositories.billing_report_repo import BillingReportRepository
    from app.registry.constants import USAGE_KEY_BUFFER_DAYS

    async with _dispatch_once("billing_reports") as claimed:
        if not claimed:
            return {"dispatched": 0}
        async with _worker_session() as session:
            repo = BillingReportRepository(session)
            pending = await repo.pending_ids()
            closures = await repo.recent_closures(datetime.now(timezone.utc) - timedelta(days=USAGE_KEY_BUFFER_DAYS))
        for report_id in pending:
            deliver_billing_report.delay(str(report_id))
        for org_id, start, end, report_id in closures:
            check_closed_billing_period.delay(str(org_id), start.isoformat(), end.isoformat(), str(report_id))
        return {"dispatched": len(pending) + len(closures)}


@celery.task(name="deliver_billing_report", rate_limit="10/s", soft_time_limit=300, time_limit=360)
def deliver_billing_report(report_id: str) -> bool:
    """Deliver one bounded batch; the DB dispatcher retries failures on its next tick."""
    return asyncio.run(_deliver_billing_report(report_id))


async def _deliver_billing_report(report_id: str) -> bool:
    from uuid import UUID

    from app.services.billing_reporting_service import BillingReportingService
    from app.services.billing_service import _ensure_stripe_configured

    _ensure_stripe_configured()
    async with _worker_session() as session:
        return await BillingReportingService(session).deliver_safely(UUID(report_id))


@celery.task(name="check_closed_billing_period")
def check_closed_billing_period(org_id: str, start: str, end: str, report_id: str) -> None:
    """Catch delayed increments without reopening the usage period or rebilling history."""
    asyncio.run(_check_closed_billing_period(org_id, start, end, report_id))


async def _check_closed_billing_period(org_id: str, start: str, end: str, report_id: str) -> None:
    from datetime import datetime, timezone
    from uuid import UUID

    import redis.asyncio as aioredis

    from app.infrastructure.db.repositories.billing_repo import BillingRepository
    from app.infrastructure.db.repositories.billing_report_repo import BillingReportRepository
    from app.services.billing_reporting_service import BillingReportingService
    from app.services.usage_service import UsageService

    async with _worker_session() as session:
        repo = BillingReportRepository(session)
        marker = await repo.lock_report(UUID(report_id))
        if marker is None:
            return
        sub = await BillingRepository(session).get_subscription_by_org(UUID(org_id))
        if sub is None:
            return
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await UsageService(redis_client, session).sync_to_database(
                sub.org_id, period_start=datetime.fromisoformat(start), period_end=datetime.fromisoformat(end)
            )
            await BillingReportingService(session).stage(sub, datetime.fromisoformat(start), allow_closed=True)
            await repo.update(marker.id, updated_at=datetime.now(timezone.utc))
            await session.commit()
        finally:
            await redis_client.aclose()


@celery.task(
    name="bill_single_org",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    rate_limit="80/s",
)
def bill_single_org(self: Any, org_id_str: str) -> dict[str, str]:
    """Worker: sync usage, compute delta, report to Stripe for one org.

    ``rate_limit="80/s"`` keeps the total Stripe API call rate across
    all workers safely below Stripe's 100 req/s live-mode limit.
    """
    from app.services.billing_service import StripeNotConfiguredError

    try:
        return asyncio.run(_bill_single_org(org_id_str))
    except StripeNotConfiguredError as exc:
        logger.error("bill_single_org_misconfigured", org_id=org_id_str, error=str(exc))
        return {"org_id": org_id_str, "status": "stripe_not_configured"}
    except Exception as exc:
        logger.error("bill_single_org_failed", org_id=org_id_str, error=str(exc))
        raise self.retry(exc=exc)


async def _bill_single_org(org_id_str: str) -> dict[str, str]:
    from uuid import UUID

    import redis.asyncio as aioredis

    from app.services.billing_service import BillingService
    from app.services.usage_service import UsageService

    org_id = UUID(org_id_str)
    async with _worker_session() as session:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            billing_svc = BillingService(session, redis_client=redis_client)
            usage_svc = UsageService(redis_client, session)

            if not await billing_svc.acquire_overage_lock(org_id):
                logger.info("bill_single_org_skipped_locked", org_id=org_id_str)
                return {"org_id": org_id_str, "status": "skipped_locked"}

            try:
                await usage_svc.sync_to_database(org_id)
                await session.flush()
                reported = await billing_svc.report_overages_to_stripe(org_id)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await billing_svc.release_overage_lock(org_id)
        finally:
            await redis_client.aclose()

    return {"org_id": org_id_str, "status": "reported" if reported else "no_overage"}


# -- HOBBY period reset -------------------------------------------------------


@celery.task(name="dispatch_hobby_reset", bind=True, max_retries=0)
def dispatch_hobby_reset(self: Any) -> dict[str, Any]:
    """Dispatcher: query HOBBY org IDs due for reset and fan out tasks."""
    try:
        return asyncio.run(_dispatch_hobby_reset())
    except Exception as exc:
        logger.error("dispatch_hobby_reset_failed", error=str(exc))
        return {"error": str(exc)}


async def _dispatch_hobby_reset() -> dict[str, Any]:
    from datetime import datetime, timezone

    from app.infrastructure.db.repositories.billing_repo import BillingRepository

    now = datetime.now(timezone.utc)
    async with _dispatch_once("hobby_reset") as claimed:
        if not claimed:
            logger.info("dispatch_hobby_reset_skipped_duplicate")
            return {"status": "skipped_duplicate", "count": 0}

        async with _worker_session() as session:
            org_ids = await BillingRepository(session).list_hobby_org_ids_due_for_reset(now)

        for oid in org_ids:
            reset_single_hobby_org.delay(str(oid))

    logger.info("dispatch_hobby_reset_done", dispatched=len(org_ids))
    return {"status": "dispatched", "count": len(org_ids)}


@celery.task(name="reset_single_hobby_org", bind=True, max_retries=2, default_retry_delay=10)
def reset_single_hobby_org(self: Any, org_id_str: str) -> dict[str, str]:
    """Worker: advance period and clear Redis counters for one HOBBY org."""
    try:
        return asyncio.run(_reset_single_hobby_org(org_id_str))
    except Exception as exc:
        logger.error("reset_single_hobby_org_failed", org_id=org_id_str, error=str(exc))
        raise self.retry(exc=exc)


async def _reset_single_hobby_org(org_id_str: str) -> dict[str, str]:
    from datetime import timedelta
    from uuid import UUID

    import redis.asyncio as aioredis

    from app.infrastructure.db.repositories.billing_repo import BillingRepository
    from app.services.usage_service import UsageService

    org_id = UUID(org_id_str)
    async with _worker_session() as session:
        billing_repo = BillingRepository(session)
        sub = await billing_repo.get_subscription_by_org(org_id)
        if sub is None:
            return {"org_id": org_id_str, "status": "no_subscription"}

        new_start = sub.current_period_end
        new_end = new_start + timedelta(days=30)

        await billing_repo.advance_period(org_id, new_start, new_end)
        await billing_repo.create_usage_record(org_id, new_start, new_end)
        await session.commit()

        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            usage_svc = UsageService(redis_client, session)
            await usage_svc.delete_usage_key(org_id, sub.current_period_start)
            await usage_svc.invalidate_subscription_cache(org_id)
        finally:
            await redis_client.aclose()

    return {"org_id": org_id_str, "status": "reset"}


# ---------------------------------------------------------------------------
# Email – welcome sequence
# ---------------------------------------------------------------------------

_email_task_opts = dict(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    rate_limit="2/s",
)


@celery.task(name="send_welcome_email", **_email_task_opts)
def send_welcome_email_task(email: str) -> dict[str, str]:
    """Schedule a welcome email via Resend for a new signup."""
    from app.services.email_service import EmailService

    svc = EmailService()
    if not svc.is_configured():
        return {"status": "skipped", "reason": "resend_not_configured"}

    svc.send_welcome_email(to=email)
    return {"status": "sent", "email": email}


@celery.task(name="send_followup_email", **_email_task_opts)
def send_followup_email_task(email: str) -> dict[str, str]:
    """Schedule a follow-up email via Resend for a new signup."""
    from app.services.email_service import EmailService

    svc = EmailService()
    if not svc.is_configured():
        return {"status": "skipped", "reason": "resend_not_configured"}

    svc.send_followup_email(to=email)
    return {"status": "sent", "email": email}


@celery.task(name="send_invitation_email", **_email_task_opts)
def send_invitation_email_task(to: str, org_name: str, inviter_name: str, role: str, app_url: str) -> dict[str, str]:
    """Send an invitation notification email via Resend."""
    from app.services.email_service import EmailService

    svc = EmailService()
    if not svc.is_configured():
        return {"status": "skipped", "reason": "resend_not_configured"}

    svc.send_invitation_email(to=to, org_name=org_name, inviter_name=inviter_name, role=role, app_url=app_url)
    return {"status": "sent", "email": to}


# ---------------------------------------------------------------------------
# Invitation housekeeping
# ---------------------------------------------------------------------------


async def _expire_stale_invitations() -> dict[str, Any]:
    from app.infrastructure.db.repositories.invitation_repo import InvitationRepository

    async with _worker_session() as session:
        count = await InvitationRepository(session).expire_stale_invitations()
        await session.commit()

    logger.info("expire_stale_invitations_done", expired=count)
    return {"status": "done", "expired": count}


@celery.task(name="expire_stale_invitations", bind=True, max_retries=0)
def expire_stale_invitations_task(self: Any) -> dict[str, Any]:
    """Periodic: transition PENDING invitations past their expiry to EXPIRED."""
    try:
        return asyncio.run(_expire_stale_invitations())
    except Exception as exc:
        logger.error("expire_stale_invitations_failed", error=str(exc))
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# CRM – Attio contact sync
# ---------------------------------------------------------------------------


@celery.task(
    name="sync_new_user_to_crm",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    rate_limit="2/s",
)
def sync_new_user_to_crm(email: str) -> dict[str, str]:
    """Assert a person record in Attio and add them to the signups list."""
    from app.services.crm_service import CrmService

    svc = CrmService()
    if not svc.is_configured():
        logger.debug("attio_skip_unconfigured", email=email)
        return {"status": "skipped", "reason": "attio_not_configured"}

    svc.sync_contact(email=email)
    return {"status": "synced", "email": email}
