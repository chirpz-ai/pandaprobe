"""Unit tests for the evaluation domain layer (no DB or LLM calls)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.api.v1.routes.evaluations import CreateTraceScoreRequest
from app.core.evals.entities import EvalRun, TraceScore, validate_score_value
from app.core.evals.metrics import get_metric, get_metric_info, list_metrics
from app.core.evals.metrics.base import MetricResult
from app.registry.constants import EvaluationStatus, ScoreDataType, ScoreSource, ScoreStatus


ALL_METRIC_NAMES = [
    "argument_correctness",
    "coherence",
    "confidence",
    "plan_adherence",
    "plan_quality",
    "step_efficiency",
    "task_completion",
    "tool_correctness",
]


def test_list_metrics_returns_all():
    names = list_metrics()
    assert names == ALL_METRIC_NAMES


def test_get_metric_returns_class():
    cls = get_metric("task_completion")
    assert cls.name == "task_completion"


def test_get_metric_info_returns_dict():
    info = get_metric_info("task_completion")
    assert info["name"] == "task_completion"
    assert "description" in info
    assert info["category"] == "trace"
    assert info["default_threshold"] == 0.5


def test_task_completion_attributes():
    cls = get_metric("task_completion")
    instance = cls()
    assert instance.name == "task_completion"
    assert instance.category == "trace"
    assert instance.threshold == 0.5
    assert instance.description != ""


def test_tool_correctness_attributes():
    cls = get_metric("tool_correctness")
    instance = cls()
    assert instance.name == "tool_correctness"
    assert instance.category == "trace"
    assert instance.threshold == 0.5
    assert instance.description != ""


def test_argument_correctness_attributes():
    cls = get_metric("argument_correctness")
    instance = cls()
    assert instance.name == "argument_correctness"
    assert instance.category == "trace"


def test_step_efficiency_attributes():
    cls = get_metric("step_efficiency")
    instance = cls()
    assert instance.name == "step_efficiency"
    assert instance.category == "trace"


def test_plan_adherence_attributes():
    cls = get_metric("plan_adherence")
    instance = cls()
    assert instance.name == "plan_adherence"
    assert instance.category == "trace"


def test_plan_quality_attributes():
    cls = get_metric("plan_quality")
    instance = cls()
    assert instance.name == "plan_quality"
    assert instance.category == "trace"


def test_trace_score_creation():
    now = datetime.now(timezone.utc)
    score = TraceScore(
        id=uuid4(),
        trace_id=uuid4(),
        project_id=uuid4(),
        name="task_completion",
        data_type=ScoreDataType.NUMERIC,
        value="0.85",
        source=ScoreSource.AUTOMATED,
        created_at=now,
        updated_at=now,
    )
    assert score.name == "task_completion"
    assert score.value == "0.85"
    assert score.source == ScoreSource.AUTOMATED


def test_trace_score_boolean():
    now = datetime.now(timezone.utc)
    score = TraceScore(
        id=uuid4(),
        trace_id=uuid4(),
        project_id=uuid4(),
        name="is_correct",
        data_type=ScoreDataType.BOOLEAN,
        value="true",
        source=ScoreSource.ANNOTATION,
        created_at=now,
        updated_at=now,
    )
    assert score.data_type == ScoreDataType.BOOLEAN


def test_trace_score_categorical():
    now = datetime.now(timezone.utc)
    score = TraceScore(
        id=uuid4(),
        trace_id=uuid4(),
        project_id=uuid4(),
        name="quality",
        data_type=ScoreDataType.CATEGORICAL,
        value="PASS",
        source=ScoreSource.PROGRAMMATIC,
        created_at=now,
        updated_at=now,
    )
    assert score.data_type == ScoreDataType.CATEGORICAL
    assert score.value == "PASS"


def test_create_trace_score_request_rejects_numeric_out_of_range():
    """Invalid NUMERIC values are rejected at API layer (422, not 500)."""
    with pytest.raises(ValueError, match="NUMERIC score must be in"):
        CreateTraceScoreRequest(
            trace_id=uuid4(),
            name="task_completion",
            value="1.5",
            data_type=ScoreDataType.NUMERIC,
        )


def test_create_trace_score_request_rejects_invalid_boolean():
    """Invalid BOOLEAN values are rejected at API layer."""
    with pytest.raises(ValueError, match="BOOLEAN score must be"):
        CreateTraceScoreRequest(
            trace_id=uuid4(),
            name="is_correct",
            value="yes",
            data_type=ScoreDataType.BOOLEAN,
        )


def test_create_trace_score_request_accepts_valid_values():
    """Valid NUMERIC, BOOLEAN, and CATEGORICAL values pass."""
    tid = uuid4()
    CreateTraceScoreRequest(trace_id=tid, name="m", value="0.85", data_type=ScoreDataType.NUMERIC)
    CreateTraceScoreRequest(trace_id=tid, name="m", value="true", data_type=ScoreDataType.BOOLEAN)
    CreateTraceScoreRequest(trace_id=tid, name="m", value="PASS", data_type=ScoreDataType.CATEGORICAL)


def test_validate_score_value_numeric():
    """validate_score_value enforces NUMERIC rules."""
    validate_score_value("0.5", ScoreDataType.NUMERIC)
    validate_score_value("0", ScoreDataType.NUMERIC)
    validate_score_value("1.0", ScoreDataType.NUMERIC)
    with pytest.raises(ValueError, match="valid number"):
        validate_score_value("hello", ScoreDataType.NUMERIC)
    with pytest.raises(ValueError, match="in \\[0.0, 1.0\\]"):
        validate_score_value("1.5", ScoreDataType.NUMERIC)
    with pytest.raises(ValueError, match="in \\[0.0, 1.0\\]"):
        validate_score_value("-0.1", ScoreDataType.NUMERIC)


def test_validate_score_value_boolean():
    """validate_score_value enforces BOOLEAN rules."""
    validate_score_value("true", ScoreDataType.BOOLEAN)
    validate_score_value("false", ScoreDataType.BOOLEAN)
    validate_score_value("TRUE", ScoreDataType.BOOLEAN)
    with pytest.raises(ValueError, match="'true' or 'false'"):
        validate_score_value("yes", ScoreDataType.BOOLEAN)


def test_validate_score_value_categorical():
    """validate_score_value accepts any string for CATEGORICAL."""
    validate_score_value("GOOD", ScoreDataType.CATEGORICAL)
    validate_score_value("PASS", ScoreDataType.CATEGORICAL)
    validate_score_value("anything", ScoreDataType.CATEGORICAL)


def test_eval_run_creation():
    now = datetime.now(timezone.utc)
    run = EvalRun(
        id=uuid4(),
        project_id=uuid4(),
        metric_names=["task_completion", "tool_correctness"],
        status=EvaluationStatus.PENDING,
        total_targets=10,
        created_at=now,
    )
    assert run.status == EvaluationStatus.PENDING
    assert len(run.metric_names) == 2
    assert run.total_targets == 10
    assert run.sampling_rate == 1.0


def test_metric_result_model():
    result = MetricResult(score=0.75, reason="Good result", metadata={"key": "value"})
    assert result.score == 0.75
    assert result.reason == "Good result"
    assert result.metadata == {"key": "value"}


def test_score_source_values():
    assert ScoreSource.AUTOMATED == "AUTOMATED"
    assert ScoreSource.ANNOTATION == "ANNOTATION"
    assert ScoreSource.PROGRAMMATIC == "PROGRAMMATIC"


def test_score_status_values():
    assert ScoreStatus.SUCCESS == "SUCCESS"
    assert ScoreStatus.FAILED == "FAILED"
    assert ScoreStatus.PENDING == "PENDING"


def test_score_data_type_values():
    assert ScoreDataType.NUMERIC == "NUMERIC"
    assert ScoreDataType.BOOLEAN == "BOOLEAN"
    assert ScoreDataType.CATEGORICAL == "CATEGORICAL"


def test_evaluation_status_unchanged():
    assert EvaluationStatus.PENDING == "PENDING"
    assert EvaluationStatus.RUNNING == "RUNNING"
    assert EvaluationStatus.COMPLETED == "COMPLETED"
    assert EvaluationStatus.FAILED == "FAILED"
