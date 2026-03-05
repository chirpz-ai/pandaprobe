"""Metric registry.

Every concrete metric class decorates itself with ``@register_metric``
so that the eval service can look up metrics by name at runtime.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.evals.metrics.base import BaseMetric

_REGISTRY: dict[str, type["BaseMetric"]] = {}


def register_metric(name: str):
    """Class decorator that adds a metric to the global registry."""

    def _wrap(cls: type["BaseMetric"]) -> type["BaseMetric"]:
        _REGISTRY[name] = cls
        return cls

    return _wrap


def get_metric(name: str) -> type["BaseMetric"]:
    """Retrieve a registered metric class by name.

    Raises:
        KeyError: If the metric name is not registered.
    """
    if name not in _REGISTRY:
        _import_builtin_metrics()
    return _REGISTRY[name]


def list_metrics() -> list[str]:
    """Return the names of all registered metrics."""
    _import_builtin_metrics()
    return sorted(_REGISTRY.keys())


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
    """Force-import every built-in metric module to trigger registration."""
    import app.core.evals.metrics.trace.argument_correctness.metric  # noqa: F401
    import app.core.evals.metrics.trace.plan_adherence.metric  # noqa: F401
    import app.core.evals.metrics.trace.plan_quality.metric  # noqa: F401
    import app.core.evals.metrics.trace.step_efficiency.metric  # noqa: F401
    import app.core.evals.metrics.trace.task_completion.metric  # noqa: F401
    import app.core.evals.metrics.trace.tool_correctness.metric  # noqa: F401
