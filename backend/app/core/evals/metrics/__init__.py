"""Metric registry.

Every concrete metric class decorates itself with ``@register_metric``
so that the eval service can look up metrics by name at runtime.
"""

from typing import TYPE_CHECKING

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
        # Ensure all built-in metrics are imported so the registry is populated.
        _import_builtin_metrics()
    return _REGISTRY[name]


def list_metrics() -> list[str]:
    """Return the names of all registered metrics."""
    _import_builtin_metrics()
    return sorted(_REGISTRY.keys())


def _import_builtin_metrics() -> None:
    """Force-import every built-in metric module to trigger registration."""
    import app.core.evals.metrics.task_completion.metric  # noqa: F401
