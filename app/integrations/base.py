"""Abstract base class for framework trace transformers.

Each agent-building framework (LangChain, LangGraph, CrewAI, etc.)
produces traces in its own format.  A transformer normalises that
format into Opentracer's universal ``Trace`` model so that all
traces look identical once stored.

Adding a new integration:
    1. Create ``app/integrations/<framework>.py``.
    2. Subclass ``BaseTraceTransformer``.
    3. Implement ``transform()`` and ``validate_payload()``.
    4. Decorate the class with ``@register_integration("<name>")``.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.core.traces.entities import Trace


class BaseTraceTransformer(ABC):
    """Contract that every framework integration must fulfill."""

    @property
    @abstractmethod
    def framework_name(self) -> str:
        """Human-readable framework identifier (e.g. ``'langchain'``)."""
        ...

    @abstractmethod
    def validate_payload(self, raw: dict[str, Any]) -> bool:
        """Return ``True`` if *raw* looks like a payload from this framework.

        Used for auto-detection when the caller does not specify a source.
        """
        ...

    @abstractmethod
    def transform(self, raw: dict[str, Any], org_id: UUID) -> Trace:
        """Convert a framework-specific payload into a universal Trace.

        Args:
            raw: The raw JSON body sent by the client.
            org_id: The authenticated organisation's ID (injected by the API).

        Returns:
            A fully-formed ``Trace`` entity ready for persistence.
        """
        ...
