"""Shared utilities for evaluation metrics."""

from __future__ import annotations

import json


def to_text(value: object) -> str:
    """Serialize a trace input/output value to a plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)
