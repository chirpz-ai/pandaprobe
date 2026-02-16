"""Abstract repository interface for the Identity domain.

Infrastructure implementations (e.g. PostgreSQL) must satisfy this
protocol so that the service layer never depends on a concrete database.
"""

from typing import Protocol
from uuid import UUID

from app.core.identity.entities import APIKey, Organization


class AbstractIdentityRepository(Protocol):
    """Port that any identity persistence adapter must implement."""

    # -- Organisation ---------------------------------------------------------

    async def create_organization(self, name: str) -> Organization:
        """Persist a new organisation and return its domain entity."""
        ...

    async def get_organization(self, org_id: UUID) -> Organization | None:
        """Fetch an organisation by primary key, or ``None``."""
        ...

    # -- API Keys -------------------------------------------------------------

    async def create_api_key(
        self,
        org_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
    ) -> APIKey:
        """Store a new API key record and return the domain entity."""
        ...

    async def get_api_key_by_hash(self, key_hash: str) -> APIKey | None:
        """Look up an **active** API key by its SHA-256 hash."""
        ...

    async def touch_api_key(self, key_id: UUID) -> None:
        """Update ``last_used_at`` to the current UTC time."""
        ...

    async def revoke_api_key(self, key_id: UUID) -> None:
        """Deactivate an API key (soft-delete)."""
        ...

    async def list_api_keys(self, org_id: UUID) -> list[APIKey]:
        """Return all API keys belonging to an organisation."""
        ...
