"""LangGraph trace transformer.

LangGraph extends LangChain, so its traces share a similar structure
but may include graph-specific metadata (node names, edge transitions,
checkpoints).  This transformer handles the LangGraph-specific
envelope while reusing the core run-tree walking logic.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.traces.entities import Span, Trace
from app.integrations import register_integration
from app.integrations.base import BaseTraceTransformer
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus

_NODE_TYPE_TO_SPAN_KIND: dict[str, SpanKind] = {
    "agent": SpanKind.AGENT,
    "tool": SpanKind.TOOL,
    "llm": SpanKind.LLM,
    "retriever": SpanKind.RETRIEVER,
    "chain": SpanKind.CHAIN,
}


@register_integration("langgraph")
class LangGraphTransformer(BaseTraceTransformer):
    """Transform LangGraph execution traces into universal traces."""

    @property
    def framework_name(self) -> str:
        """Return the framework identifier."""
        return "langgraph"

    def validate_payload(self, raw: dict[str, Any]) -> bool:
        """Detect LangGraph payloads by graph-specific keys."""
        return "nodes" in raw or ("run_type" in raw and raw.get("extra", {}).get("graph_id") is not None)

    def transform(self, raw: dict[str, Any], org_id: UUID) -> Trace:
        """Convert a LangGraph trace into a Trace with nested Spans."""
        trace_id = uuid4()
        spans: list[Span] = []

        # LangGraph may expose nodes as a flat list or as a nested run tree.
        nodes = raw.get("nodes", [])
        if nodes:
            for node in nodes:
                self._node_to_span(node, trace_id=trace_id, parent_span_id=None, spans=spans)
        elif "child_runs" in raw:
            self._walk_runs(raw, trace_id=trace_id, parent_span_id=None, spans=spans)

        return Trace(
            trace_id=trace_id,
            org_id=org_id,
            name=raw.get("name", raw.get("graph_id", "langgraph-trace")),
            status=TraceStatus.COMPLETED if raw.get("error") is None else TraceStatus.ERROR,
            input=raw.get("inputs", raw.get("input")),
            output=raw.get("outputs", raw.get("output")),
            metadata={"source": "langgraph", "graph_id": raw.get("graph_id")},
            started_at=_parse_ts(raw.get("start_time")),
            ended_at=_parse_ts(raw.get("end_time")),
            spans=spans,
        )

    def _node_to_span(
        self,
        node: dict[str, Any],
        trace_id: UUID,
        parent_span_id: UUID | None,
        spans: list[Span],
    ) -> None:
        """Convert a graph node into a Span."""
        span_id = uuid4()
        node_type = node.get("type", "chain")

        spans.append(
            Span(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=node.get("name", node_type),
                kind=_NODE_TYPE_TO_SPAN_KIND.get(node_type, SpanKind.OTHER),
                status=SpanStatusCode.ERROR if node.get("error") else SpanStatusCode.OK,
                input=node.get("input"),
                output=node.get("output"),
                metadata={"node_type": node_type},
                started_at=_parse_ts(node.get("start_time")),
                ended_at=_parse_ts(node.get("end_time")),
            )
        )

        for child in node.get("children", []):
            self._node_to_span(child, trace_id=trace_id, parent_span_id=span_id, spans=spans)

    def _walk_runs(
        self,
        run: dict[str, Any],
        trace_id: UUID,
        parent_span_id: UUID | None,
        spans: list[Span],
    ) -> None:
        """Fallback: walk a LangChain-style run tree."""
        span_id = uuid4()
        run_type = run.get("run_type", "chain")

        spans.append(
            Span(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=run.get("name", run_type),
                kind=_NODE_TYPE_TO_SPAN_KIND.get(run_type, SpanKind.OTHER),
                status=SpanStatusCode.ERROR if run.get("error") else SpanStatusCode.OK,
                input=run.get("inputs"),
                output=run.get("outputs"),
                metadata={"run_type": run_type},
                started_at=_parse_ts(run.get("start_time")),
                ended_at=_parse_ts(run.get("end_time")),
            )
        )

        for child in run.get("child_runs", []):
            self._walk_runs(child, trace_id=trace_id, parent_span_id=span_id, spans=spans)


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
