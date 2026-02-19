"""Abstract repository interface for the Traces domain.

Infrastructure implementations must satisfy this protocol so that
services never depend on a concrete database driver.
"""

from typing import Protocol
from uuid import UUID

from app.core.traces.entities import Trace


class AbstractTraceRepository(Protocol):
    """Port that any trace persistence adapter must implement."""

    async def create_trace(self, trace: Trace) -> Trace:
        """Persist a full trace (including its spans) and return it."""
        ...

    async def get_trace(self, trace_id: UUID, org_id: UUID) -> Trace | None:
        """Fetch a single trace with all its spans."""
        ...

    async def list_traces(
        self,
        org_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Trace]:
        """Return traces belonging to an organization, newest first."""
        ...
