"""Framework integration registry.

Each integration transforms a framework-specific trace payload into
Opentracer's universal ``Trace`` / ``Span`` format.  Register new
integrations by subclassing ``BaseTraceTransformer`` and decorating
with ``@register_integration``.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.base import BaseTraceTransformer

_REGISTRY: dict[str, type["BaseTraceTransformer"]] = {}


def register_integration(name: str):
    """Class decorator that registers a framework integration."""

    def _wrap(cls: type["BaseTraceTransformer"]) -> type["BaseTraceTransformer"]:
        _REGISTRY[name] = cls
        return cls

    return _wrap


def get_integration(name: str) -> type["BaseTraceTransformer"]:
    """Retrieve a registered integration by framework name.

    Raises:
        KeyError: If the integration name is not registered.
    """
    if name not in _REGISTRY:
        _import_builtin_integrations()
    return _REGISTRY[name]


def list_integrations() -> list[str]:
    """Return the names of all registered integrations."""
    _import_builtin_integrations()
    return sorted(_REGISTRY.keys())


def _import_builtin_integrations() -> None:
    """Force-import all built-in integration modules."""
    import app.integrations.langchain  # noqa: F401
    import app.integrations.langgraph  # noqa: F401
    import app.integrations.crewai  # noqa: F401
