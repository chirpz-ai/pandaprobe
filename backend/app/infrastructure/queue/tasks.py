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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.queue.celery_app import celery
from app.logging import logger
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


@celery.task(name="execute_eval_run", bind=True, max_retries=2, default_retry_delay=10)
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
    lock = redis_client.lock("check_eval_monitors", timeout=60)
    if not lock.acquire(blocking=False):
        logger.info("check_eval_monitors_skipped", reason="lock held by another worker")
        return {"status": "skipped", "reason": "lock"}

    try:
        now = datetime.now(timezone.utc)

        async with _worker_session() as session:
            eval_repo = EvalRepository(session)
            due_monitors = await eval_repo.get_due_monitors(now)

            dispatched = 0
            for monitor in due_monitors:
                next_run = compute_next_run(monitor.cadence, now)
                await eval_repo.reschedule_monitor(
                    monitor.id,
                    next_run_at=next_run,
                )
                await session.commit()

                process_single_monitor.delay(str(monitor.id), str(monitor.project_id))
                dispatched += 1

        summary = {"status": "completed", "dispatched": dispatched}
        logger.info("check_eval_monitors_done", **summary)
        return summary

    finally:
        try:
            lock.release()
        except Exception:
            pass


@celery.task(name="process_single_monitor", bind=True, max_retries=2, default_retry_delay=30)
def process_single_monitor(self: Any, monitor_id: str, project_id: str) -> dict[str, str]:
    """Process a single due monitor: check for new data, spawn an eval run if needed.

    Runs as an independent task so multiple monitors execute in parallel
    across all available worker slots.
    """
    try:
        return asyncio.run(_process_single_monitor(monitor_id, project_id))
    except Exception as exc:
        logger.error("process_single_monitor_failed", monitor_id=monitor_id, error=str(exc))
        raise self.retry(exc=exc)


async def _process_single_monitor(monitor_id: str, project_id: str) -> dict[str, str]:
    from datetime import datetime, timezone
    from uuid import UUID

    from app.core.evals.cadence import compute_next_run
    from app.infrastructure.db.repositories.eval_repo import EvalRepository
    from app.services.eval_service import EvalService

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

        run = await svc._spawn_run_for_monitor(monitor)

        now = datetime.now(timezone.utc)
        next_run = compute_next_run(monitor.cadence, now)
        await eval_repo.advance_monitor(
            mid,
            last_run_at=now,
            last_run_id=run.id,
            next_run_at=next_run,
        )
        await session.commit()

        logger.info(
            "monitor_run_spawned",
            monitor_id=monitor_id,
            run_id=str(run.id),
            next_run_at=next_run.isoformat(),
        )
        return {"monitor_id": monitor_id, "status": "spawned", "run_id": str(run.id)}


# ---------------------------------------------------------------------------
# Session eval run execution
# ---------------------------------------------------------------------------

SIGNAL_METRICS = ["confidence", "coherence", "loop_detection", "tool_correctness"]


@celery.task(name="execute_session_eval_run", bind=True, max_retries=2, default_retry_delay=10)
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
    import json as _json
    from datetime import datetime, timezone
    from uuid import UUID, uuid4

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.evals.entities import SessionScore, TraceScore
    from app.core.evals.metrics import get_metric, get_session_metric
    from app.core.evals.metrics.base import MetricResult
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
            def _to_text(val: object) -> str:
                if val is None:
                    return ""
                if isinstance(val, str):
                    return val
                return _json.dumps(val, default=str)

            all_texts = []
            for t in traces:
                inp = _to_text(t.input)
                out = _to_text(t.output)
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
