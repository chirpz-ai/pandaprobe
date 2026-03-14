"""Unit tests for the session evaluation domain layer (no DB or LLM calls)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.evals.entities import SessionScore, validate_score_value
from app.core.evals.metrics import get_session_metric, list_session_metrics
from app.core.evals.metrics.base import DEFAULT_SIGNAL_WEIGHTS, BaseSessionMetric, MetricResult
from app.registry.constants import ScoreDataType, ScoreSource, ScoreStatus


ALL_SESSION_METRIC_NAMES = [
    "agent_consistency",
    "agent_reliability",
]


def test_list_session_metrics_returns_all():
    names = list_session_metrics()
    assert names == ALL_SESSION_METRIC_NAMES


def test_get_session_metric_returns_class():
    cls = get_session_metric("agent_reliability")
    assert cls.name == "agent_reliability"
    assert issubclass(cls, BaseSessionMetric)


def test_agent_reliability_attributes():
    cls = get_session_metric("agent_reliability")
    instance = cls()
    assert instance.name == "agent_reliability"
    assert instance.category == "session"
    assert instance.threshold == 0.5
    assert instance.description != ""


def test_agent_consistency_attributes():
    cls = get_session_metric("agent_consistency")
    instance = cls()
    assert instance.name == "agent_consistency"
    assert instance.category == "session"
    assert instance.threshold == 0.5
    assert instance.description != ""


def test_session_score_creation():
    now = datetime.now(timezone.utc)
    score = SessionScore(
        id=uuid4(),
        session_id="session-abc",
        project_id=uuid4(),
        name="agent_reliability",
        data_type=ScoreDataType.NUMERIC,
        value="0.85",
        source=ScoreSource.AUTOMATED,
        created_at=now,
        updated_at=now,
    )
    assert score.name == "agent_reliability"
    assert score.value == "0.85"
    assert score.source == ScoreSource.AUTOMATED
    assert score.session_id == "session-abc"


def test_session_score_rejects_out_of_range():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="in \\[0.0, 1.0\\]"):
        SessionScore(
            id=uuid4(),
            session_id="session-abc",
            project_id=uuid4(),
            name="agent_reliability",
            data_type=ScoreDataType.NUMERIC,
            value="1.5",
            source=ScoreSource.AUTOMATED,
            created_at=now,
            updated_at=now,
        )


def test_session_score_allows_none_value():
    now = datetime.now(timezone.utc)
    score = SessionScore(
        id=uuid4(),
        session_id="session-abc",
        project_id=uuid4(),
        name="agent_reliability",
        data_type=ScoreDataType.NUMERIC,
        value=None,
        source=ScoreSource.AUTOMATED,
        status=ScoreStatus.FAILED,
        created_at=now,
        updated_at=now,
    )
    assert score.value is None
    assert score.status == ScoreStatus.FAILED


def test_default_signal_weights():
    assert "confidence" in DEFAULT_SIGNAL_WEIGHTS
    assert "loop_detection" in DEFAULT_SIGNAL_WEIGHTS
    assert "tool_correctness" in DEFAULT_SIGNAL_WEIGHTS
    assert "coherence" in DEFAULT_SIGNAL_WEIGHTS
    assert all(isinstance(v, float) for v in DEFAULT_SIGNAL_WEIGHTS.values())


# -- AgentReliability pure-math tests -----------------------------------------


@pytest.mark.asyncio
async def test_agent_reliability_empty_session():
    cls = get_session_metric("agent_reliability")
    metric = cls()
    result = await metric.evaluate("sid", [], None, precomputed_signals=None)
    assert result.score == 1.0
    assert "empty" in (result.metadata.get("note", "") or result.reason).lower()


@pytest.mark.asyncio
async def test_agent_reliability_perfect_signals():
    from app.core.traces.entities import Trace

    traces = [
        Trace(
            trace_id=uuid4(),
            project_id=uuid4(),
            name=f"trace-{i}",
            started_at=datetime.now(timezone.utc),
            spans=[],
        )
        for i in range(3)
    ]
    signals = {
        str(t.trace_id): {
            "confidence": 1.0,
            "loop_detection": 1.0,
            "tool_correctness": 1.0,
            "coherence": 1.0,
        }
        for t in traces
    }
    cls = get_session_metric("agent_reliability")
    metric = cls()
    result = await metric.evaluate("sid", traces, None, precomputed_signals=signals)
    assert result.score == 1.0
    assert "No elevated risk" in result.reason


@pytest.mark.asyncio
async def test_agent_reliability_high_risk():
    from app.core.traces.entities import Trace

    traces = [
        Trace(
            trace_id=uuid4(),
            project_id=uuid4(),
            name="risky-trace",
            started_at=datetime.now(timezone.utc),
            spans=[],
        )
    ]
    signals = {
        str(traces[0].trace_id): {
            "confidence": 0.1,
            "loop_detection": 0.1,
            "tool_correctness": 0.1,
            "coherence": 0.1,
        }
    }
    cls = get_session_metric("agent_reliability")
    metric = cls()
    result = await metric.evaluate("sid", traces, None, precomputed_signals=signals)
    assert result.score < 0.3
    assert "Elevated risk" in result.reason


# -- AgentConsistency pure-math tests -----------------------------------------


@pytest.mark.asyncio
async def test_agent_consistency_empty_session():
    cls = get_session_metric("agent_consistency")
    metric = cls()
    result = await metric.evaluate("sid", [], None, precomputed_signals=None)
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_agent_consistency_perfect_signals():
    from app.core.traces.entities import Trace

    traces = [
        Trace(
            trace_id=uuid4(),
            project_id=uuid4(),
            name=f"trace-{i}",
            started_at=datetime.now(timezone.utc),
            spans=[],
        )
        for i in range(3)
    ]
    signals = {
        str(t.trace_id): {
            "confidence": 1.0,
            "loop_detection": 1.0,
            "tool_correctness": 1.0,
            "coherence": 1.0,
        }
        for t in traces
    }
    cls = get_session_metric("agent_consistency")
    metric = cls()
    result = await metric.evaluate("sid", traces, None, precomputed_signals=signals)
    assert result.score == 1.0
    assert "consistent" in result.reason.lower()


@pytest.mark.asyncio
async def test_agent_consistency_high_instability():
    from app.core.traces.entities import Trace

    traces = [
        Trace(
            trace_id=uuid4(),
            project_id=uuid4(),
            name="unstable-trace",
            started_at=datetime.now(timezone.utc),
            spans=[],
        )
    ]
    signals = {
        str(traces[0].trace_id): {
            "confidence": 0.1,
            "loop_detection": 0.1,
            "tool_correctness": 0.1,
            "coherence": 0.1,
        }
    }
    cls = get_session_metric("agent_consistency")
    metric = cls()
    result = await metric.evaluate("sid", traces, None, precomputed_signals=signals)
    assert result.score < 0.3
    assert "instability" in result.reason.lower()


@pytest.mark.asyncio
async def test_agent_consistency_custom_weights():
    from app.core.traces.entities import Trace

    traces = [
        Trace(
            trace_id=uuid4(),
            project_id=uuid4(),
            name="trace-0",
            started_at=datetime.now(timezone.utc),
            spans=[],
        )
    ]
    signals = {
        str(traces[0].trace_id): {
            "confidence": 0.5,
            "loop_detection": 0.8,
            "tool_correctness": 0.9,
            "coherence": 0.7,
        }
    }
    cls = get_session_metric("agent_consistency")
    metric = cls()
    result_default = await metric.evaluate("sid", traces, None, precomputed_signals=signals)
    result_custom = await metric.evaluate(
        "sid",
        traces,
        None,
        precomputed_signals=signals,
        signal_weights={"confidence": 2.0, "loop_detection": 0.5, "tool_correctness": 0.1, "coherence": 0.5},
    )
    assert result_default.score != result_custom.score


# -- Trace-level signal metric attribute tests --------------------------------


def test_confidence_metric_attributes():
    from app.core.evals.metrics import get_metric

    cls = get_metric("confidence")
    instance = cls()
    assert instance.name == "confidence"
    assert instance.category == "trace"


def test_coherence_metric_attributes():
    from app.core.evals.metrics import get_metric

    cls = get_metric("coherence")
    instance = cls()
    assert instance.name == "coherence"
    assert instance.category == "trace"


def test_loop_detection_metric_attributes():
    from app.core.evals.metrics import get_metric

    cls = get_metric("loop_detection")
    instance = cls()
    assert instance.name == "loop_detection"
    assert instance.category == "trace"
