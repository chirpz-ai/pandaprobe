"""Metric registry.

Every concrete metric class decorates itself with ``@register_metric``
(trace-level) or ``@register_session_metric`` (session-level) so that
the eval service can look up metrics by name at runtime.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.evals.metrics.base import BaseMetric, BaseSessionMetric

_REGISTRY: dict[str, type["BaseMetric"]] = {}
_SESSION_REGISTRY: dict[str, type["BaseSessionMetric"]] = {}


def register_metric(name: str):
    """Class decorator that adds a trace-level metric to the global registry."""

    def _wrap(cls: type["BaseMetric"]) -> type["BaseMetric"]:
        _REGISTRY[name] = cls
        return cls

    return _wrap


def register_session_metric(name: str):
    """Class decorator that adds a session-level metric to the global registry."""

    def _wrap(cls: type["BaseSessionMetric"]) -> type["BaseSessionMetric"]:
        _SESSION_REGISTRY[name] = cls
        return cls

    return _wrap


def get_metric(name: str) -> type["BaseMetric"]:
    """Retrieve a registered trace metric class by name.

    Raises:
        KeyError: If the metric name is not registered.
    """
    if name not in _REGISTRY:
        _import_builtin_metrics()
    return _REGISTRY[name]


def get_session_metric(name: str) -> type["BaseSessionMetric"]:
    """Retrieve a registered session metric class by name.

    Raises:
        KeyError: If the metric name is not registered.
    """
    if name not in _SESSION_REGISTRY:
        _import_builtin_session_metrics()
    return _SESSION_REGISTRY[name]


def list_metrics() -> list[str]:
    """Return the names of all registered trace metrics available for standalone runs.

    Metrics that require session context (e.g. loop_detection) are excluded
    because they cannot produce meaningful results without prior traces.
    They remain accessible via ``get_metric()`` for the session-eval signal
    pipeline.
    """
    _import_builtin_metrics()
    return sorted(k for k, cls in _REGISTRY.items() if not cls.requires_session_context)


def list_session_metrics() -> list[str]:
    """Return the names of all registered session metrics."""
    _import_builtin_session_metrics()
    return sorted(_SESSION_REGISTRY.keys())


def get_metric_summary(name: str) -> dict[str, Any]:
    """Return lightweight summary (name, description, category) without expensive prompt_preview.

    Use this for list endpoints. For full info including threshold and
    prompt preview, use get_metric_info().
    """
    cls = get_metric(name)
    return {
        "name": cls.name,
        "description": cls.description,
        "category": cls.category,
    }


def get_session_metric_summary(name: str) -> dict[str, Any]:
    """Return lightweight summary for a session metric."""
    cls = get_session_metric(name)
    return {
        "name": cls.name,
        "description": cls.description,
        "category": cls.category,
    }


def get_metric_info(name: str) -> dict[str, Any]:
    """Return full metadata about a registered metric.

    Includes prompt_preview (expensive: instantiates metric and builds
    sample prompts). Use get_metric_summary() for list endpoints.
    """
    cls = get_metric(name)
    instance = cls()
    return {
        "name": instance.name,
        "description": instance.description,
        "category": instance.category,
        "default_threshold": instance.threshold,
        "prompt_preview": cls.get_prompt_preview(),
    }


def _import_builtin_metrics() -> None:
    """Force-import every built-in trace metric module to trigger registration."""
    import app.core.evals.metrics.trace.argument_correctness.metric  # noqa: F401
    import app.core.evals.metrics.trace.coherence.metric  # noqa: F401
    import app.core.evals.metrics.trace.confidence.metric  # noqa: F401
    import app.core.evals.metrics.trace.loop_detection.metric  # noqa: F401
    import app.core.evals.metrics.trace.plan_adherence.metric  # noqa: F401
    import app.core.evals.metrics.trace.plan_quality.metric  # noqa: F401
    import app.core.evals.metrics.trace.step_efficiency.metric  # noqa: F401
    import app.core.evals.metrics.trace.task_completion.metric  # noqa: F401
    import app.core.evals.metrics.trace.tool_correctness.metric  # noqa: F401


def _import_builtin_session_metrics() -> None:
    """Force-import every built-in session metric module to trigger registration."""
    import app.core.evals.metrics.session.agent_consistency.metric  # noqa: F401
    import app.core.evals.metrics.session.agent_reliability.metric  # noqa: F401
