"""Orchestration logic for the Identity domain.

Coordinates between API key generation (registry), persistence
(infrastructure), and domain validation (core).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import APIKey, Organization
from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.registry.exceptions import NotFoundError
from app.registry.security import generate_api_key, hash_api_key, key_prefix


class IdentityService:
    """Application service that manages organisations and API keys."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._repo = IdentityRepository(session)

    async def create_organization(self, name: str) -> Organization:
        """Create a new tenant organisation."""
        return await self._repo.create_organization(name=name)

    async def get_organization(self, org_id: UUID) -> Organization:
        """Retrieve an organisation or raise ``NotFoundError``."""
        org = await self._repo.get_organization(org_id)
        if org is None:
            raise NotFoundError(f"Organization {org_id} not found.")
        return org

    async def create_api_key(self, org_id: UUID, name: str) -> tuple[APIKey, str]:
        """Generate a new API key for an organisation.

        Returns:
            A tuple of (APIKey entity, raw_key_string).  The raw key
            is returned only once and must be shown to the user
            immediately; it is never stored.
        """
        # Ensure the org exists.
        await self.get_organization(org_id)

        raw_key = generate_api_key()
        hashed = hash_api_key(raw_key)
        prefix = key_prefix(raw_key)

        api_key = await self._repo.create_api_key(
            org_id=org_id,
            key_hash=hashed,
            key_prefix=prefix,
            name=name,
        )
        return api_key, raw_key

    async def list_api_keys(self, org_id: UUID) -> list[APIKey]:
        """List all API keys for an organisation."""
        await self.get_organization(org_id)
        return await self._repo.list_api_keys(org_id)

    async def revoke_api_key(self, key_id: UUID) -> None:
        """Deactivate an API key."""
        await self._repo.revoke_api_key(key_id)
