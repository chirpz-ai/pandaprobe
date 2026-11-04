"""Shared utilities for evaluation metrics."""

from __future__ import annotations

import json
import textwrap

#: Reflect rule and memory operations are neutral; task-directed mistakes remain assessable.
REFLECT_TOOL_GUIDANCE = textwrap.dedent("""\
    PandaProbe Reflect is optional. When present, `reflect_bash` (or
    `mcp__pandaprobe_reflect__reflect_bash`) may read guidance or manage an
    isolated memory filesystem. Treat these Reflect rule and memory operations
    as neutral: no credit or penalty for their presence, absence, frequency,
    or cost. Judge task actions and outcomes normally; using these tools for
    a task action does not exempt mistakes.
""")


def to_text(value: object) -> str:
    """Serialize a trace input/output value to a plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)
