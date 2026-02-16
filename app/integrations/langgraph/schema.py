"""Pydantic schemas for LangGraph trace payloads.

LangGraph extends LangChain and may produce traces either as a flat
list of graph **nodes** (each with children) or as a LangChain-style
nested **run tree** annotated with ``graph_id``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LangGraphNode(BaseModel):
    """A single node in the LangGraph execution graph."""

    name: str = "unnamed"
    type: str = "chain"
    input: Any | None = None
    output: Any | None = None
    error: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    children: list[LangGraphNode] = Field(default_factory=list)


class LangGraphEdge(BaseModel):
    """An edge transition between two nodes."""

    source: str
    target: str
    condition: str | None = None


class LangGraphTrace(BaseModel):
    """Top-level LangGraph execution trace.

    The trace may contain either a ``nodes`` list (graph-native format)
    or ``child_runs`` (LangChain-inherited format).  The transformer
    handles both.
    """

    name: str = "langgraph-trace"
    graph_id: str | None = None
    inputs: Any | None = None
    outputs: Any | None = None
    input: Any | None = None
    output: Any | None = None
    error: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    nodes: list[LangGraphNode] = Field(default_factory=list)
    edges: list[LangGraphEdge] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
