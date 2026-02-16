"""CrewAI trace transformer.

CrewAI organises work around Crews, Agents, and Tasks.  This
transformer maps that hierarchy into Opentracer's universal Span tree:

- **Crew** -> root Span (kind=AGENT)
- **Agent step** -> child Span (kind=AGENT)
- **Tool use** -> child Span (kind=TOOL)
- **LLM call** -> child Span (kind=LLM)
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.traces.entities import Span, Trace
from app.integrations import register_integration
from app.integrations.base import BaseTraceTransformer
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus


@register_integration("crewai")
class CrewAITransformer(BaseTraceTransformer):
    """Transform CrewAI execution traces into universal traces."""

    @property
    def framework_name(self) -> str:
        """Return the framework identifier."""
        return "crewai"

    def validate_payload(self, raw: dict[str, Any]) -> bool:
        """Detect CrewAI payloads by crew-specific keys."""
        return "crew" in raw or "tasks" in raw and "agents" in raw

    def transform(self, raw: dict[str, Any], org_id: UUID) -> Trace:
        """Convert a CrewAI execution trace into a universal Trace."""
        trace_id = uuid4()
        spans: list[Span] = []

        crew = raw.get("crew", {})
        crew_span_id = uuid4()

        # Root span for the crew.
        spans.append(
            Span(
                span_id=crew_span_id,
                trace_id=trace_id,
                name=crew.get("name", "crewai-crew"),
                kind=SpanKind.AGENT,
                status=SpanStatusCode.OK if raw.get("status") != "error" else SpanStatusCode.ERROR,
                input=raw.get("input"),
                output=raw.get("output"),
                metadata={"source": "crewai", "crew_id": crew.get("id")},
                started_at=_parse_ts(raw.get("start_time")),
                ended_at=_parse_ts(raw.get("end_time")),
            )
        )

        # Each task becomes a child span.
        for task in raw.get("tasks", []):
            task_span_id = uuid4()
            spans.append(
                Span(
                    span_id=task_span_id,
                    trace_id=trace_id,
                    parent_span_id=crew_span_id,
                    name=task.get("description", "task"),
                    kind=SpanKind.AGENT,
                    status=SpanStatusCode.OK if task.get("status") != "error" else SpanStatusCode.ERROR,
                    input=task.get("input"),
                    output=task.get("output"),
                    metadata={"agent": task.get("agent")},
                    started_at=_parse_ts(task.get("start_time")),
                    ended_at=_parse_ts(task.get("end_time")),
                )
            )

            # Tool calls and LLM calls within a task.
            for step in task.get("steps", []):
                step_kind = SpanKind.TOOL if step.get("type") == "tool" else SpanKind.LLM
                spans.append(
                    Span(
                        span_id=uuid4(),
                        trace_id=trace_id,
                        parent_span_id=task_span_id,
                        name=step.get("name", step.get("type", "step")),
                        kind=step_kind,
                        status=SpanStatusCode.OK if step.get("error") is None else SpanStatusCode.ERROR,
                        input=step.get("input"),
                        output=step.get("output"),
                        model=step.get("model"),
                        token_usage=step.get("token_usage"),
                        metadata={},
                        started_at=_parse_ts(step.get("start_time")),
                        ended_at=_parse_ts(step.get("end_time")),
                    )
                )

        return Trace(
            trace_id=trace_id,
            org_id=org_id,
            name=crew.get("name", "crewai-trace"),
            status=TraceStatus.COMPLETED if raw.get("status") != "error" else TraceStatus.ERROR,
            input=raw.get("input"),
            output=raw.get("output"),
            metadata={"source": "crewai"},
            started_at=_parse_ts(raw.get("start_time")),
            ended_at=_parse_ts(raw.get("end_time")),
            spans=spans,
        )


def _parse_ts(value: Any) -> datetime:
    """Best-effort timestamp parsing; falls back to now."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(timezone.utc)
