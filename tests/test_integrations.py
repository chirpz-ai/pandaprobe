"""Unit tests for framework integration transformers."""

from uuid import uuid4

from app.integrations import list_integrations, get_integration
from app.integrations.langchain import LangChainTransformer
from app.integrations.crewai import CrewAITransformer
from app.integrations._utils import parse_timestamp, safe_get
from app.registry.constants import SpanKind


def test_list_integrations() -> None:
    integrations = list_integrations()
    assert "langchain" in integrations
    assert "langgraph" in integrations
    assert "crewai" in integrations


def test_get_integration_returns_class() -> None:
    cls = get_integration("langchain")
    assert cls is LangChainTransformer


def test_langchain_validate_payload() -> None:
    transformer = LangChainTransformer()
    assert transformer.validate_payload({"run_type": "chain", "child_runs": []})
    assert not transformer.validate_payload({"random": "data"})


def test_langchain_transform_basic() -> None:
    org_id = uuid4()
    raw = {
        "name": "test-chain",
        "run_type": "chain",
        "inputs": {"query": "hello"},
        "outputs": {"answer": "world"},
        "start_time": "2025-01-01T00:00:00Z",
        "end_time": "2025-01-01T00:00:01Z",
        "child_runs": [
            {
                "name": "llm-call",
                "run_type": "llm",
                "inputs": {"prompt": "hello"},
                "outputs": {"text": "world"},
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-01-01T00:00:01Z",
                "child_runs": [],
                "extra": {
                    "invocation_params": {"model_name": "gpt-4o"},
                    "token_usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    },
                },
            }
        ],
    }
    transformer = LangChainTransformer()
    trace = transformer.transform(raw, org_id)
    assert trace.org_id == org_id
    assert trace.name == "test-chain"
    assert len(trace.spans) == 2
    assert trace.spans[0].kind == SpanKind.CHAIN
    assert trace.spans[1].kind == SpanKind.LLM
    assert trace.spans[1].parent_span_id == trace.spans[0].span_id
    assert trace.spans[1].model == "gpt-4o"
    assert trace.spans[1].token_usage is not None
    assert trace.spans[1].token_usage["total_tokens"] == 30


def test_crewai_transform_basic() -> None:
    org_id = uuid4()
    raw = {
        "crew": {"name": "research-crew", "id": "crew-1"},
        "input": {"topic": "AI safety"},
        "output": {"report": "Done"},
        "start_time": "2025-01-01T00:00:00Z",
        "end_time": "2025-01-01T00:00:10Z",
        "tasks": [
            {
                "description": "research-task",
                "agent": "researcher",
                "input": {"query": "AI safety papers"},
                "output": {"papers": 5},
                "start_time": "2025-01-01T00:00:01Z",
                "end_time": "2025-01-01T00:00:05Z",
                "steps": [
                    {
                        "type": "tool",
                        "name": "web_search",
                        "input": {"q": "AI safety"},
                        "output": {"results": 10},
                        "start_time": "2025-01-01T00:00:02Z",
                        "end_time": "2025-01-01T00:00:03Z",
                    }
                ],
            }
        ],
    }
    t = CrewAITransformer()
    trace = t.transform(raw, org_id)
    assert trace.name == "research-crew"
    assert len(trace.spans) == 3  # crew + task + tool step
    assert trace.spans[0].kind == SpanKind.AGENT  # crew
    assert trace.spans[2].kind == SpanKind.TOOL  # tool step


def test_parse_timestamp_iso() -> None:
    ts = parse_timestamp("2025-01-01T12:00:00+00:00")
    assert ts.year == 2025


def test_parse_timestamp_epoch() -> None:
    ts = parse_timestamp(1700000000.0)
    assert ts.year == 2023


def test_parse_timestamp_fallback() -> None:
    ts = parse_timestamp("not-a-date")
    assert ts is not None


def test_safe_get_nested() -> None:
    d = {"a": {"b": {"c": 42}}}
    assert safe_get(d, "a", "b", "c") == 42
    assert safe_get(d, "a", "x", default="missing") == "missing"
