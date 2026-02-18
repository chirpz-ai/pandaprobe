"""Orchestration logic for the Identity domain.

Coordinates between API key generation, persistence, and domain
validation for organisations, memberships, projects, and API keys.
"""

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import APIKey, Membership, Organization, Project
from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.infrastructure.db.repositories.project_repo import ProjectRepository
from app.registry.constants import MembershipRole
from app.registry.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.registry.security import generate_api_key, hash_api_key, key_prefix


_ROLE_RANK: dict[MembershipRole, int] = {
    MembershipRole.MEMBER: 0,
    MembershipRole.ADMIN: 1,
    MembershipRole.OWNER: 2,
}


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


class IdentityService:
    """Application service that manages organizations, memberships, and API keys."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._repo = IdentityRepository(session)
        self._project_repo = ProjectRepository(session)

    # -- Organisation ---------------------------------------------------------

    async def create_organization(self, name: str, owner_id: UUID) -> Organization:
        """Create a new tenant organisation and assign the owner membership."""
        slug = _slugify(name)
        if not slug:
            raise ValidationError("Organisation name must contain at least one alphanumeric character.")
        existing = await self._repo.get_organization_by_slug(slug)
        if existing:
            raise ConflictError(f"Organisation with slug '{slug}' already exists.")

        org = await self._repo.create_organization(name=name, slug=slug)
        await self._repo.create_membership(user_id=owner_id, org_id=org.id, role=MembershipRole.OWNER)
        return org

    async def get_organization(self, org_id: UUID) -> Organization:
        """Retrieve an organisation or raise ``NotFoundError``."""
        org = await self._repo.get_organization(org_id)
        if org is None:
            raise NotFoundError(f"Organization {org_id} not found.")
        return org

    # -- Membership -----------------------------------------------------------

    async def require_membership(self, user_id: UUID, org_id: UUID) -> Membership:
        """Ensure the user belongs to the org, or raise ``AuthorizationError``."""
        membership = await self._repo.get_membership(user_id, org_id)
        if membership is None:
            raise AuthorizationError("You are not a member of this organisation.")
        return membership

    async def require_admin(self, user_id: UUID, org_id: UUID) -> Membership:
        """Ensure the user is at least ADMIN in the org."""
        m = await self.require_membership(user_id, org_id)
        if m.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
            raise AuthorizationError("Admin or Owner role required.")
        return m

    async def add_member(
        self, org_id: UUID, user_id: UUID, role: MembershipRole = MembershipRole.MEMBER
    ) -> Membership:
        """Add a user to an organisation."""
        existing = await self._repo.get_membership(user_id, org_id)
        if existing:
            raise ConflictError("User is already a member of this organisation.")
        return await self._repo.create_membership(user_id=user_id, org_id=org_id, role=role)

    async def list_user_orgs(self, user_id: UUID) -> list[Membership]:
        """Return all memberships for a user."""
        return await self._repo.list_user_orgs(user_id)

    async def list_org_members(self, org_id: UUID) -> list[Membership]:
        """Return all members of an organisation."""
        return await self._repo.list_org_members(org_id)

    # -- Project --------------------------------------------------------------

    async def create_project(self, org_id: UUID, name: str, description: str = "") -> Project:
        """Create a new project within an organisation."""
        await self.get_organization(org_id)
        return await self._project_repo.create_project(org_id=org_id, name=name, description=description)

    async def get_project(self, project_id: UUID, *, org_id: UUID | None = None) -> Project:
        """Fetch a project or raise ``NotFoundError``.

        When *org_id* is supplied the project must belong to that
        organisation, otherwise ``AuthorizationError`` is raised.
        """
        project = await self._project_repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.")
        if org_id is not None and project.org_id != org_id:
            raise AuthorizationError("Project does not belong to this organisation.")
        return project

    async def list_projects(self, org_id: UUID) -> list[Project]:
        """List all projects for an organisation."""
        return await self._project_repo.list_projects(org_id)

    # -- API Keys -------------------------------------------------------------

    async def create_api_key(
        self,
        org_id: UUID,
        project_id: UUID,
        name: str,
        created_by: UUID | None = None,
    ) -> tuple[APIKey, str]:
        """Generate a new API key scoped to a project.

        Returns:
            A tuple of (APIKey entity, raw_key_string).
        """
        await self.get_organization(org_id)
        await self.get_project(project_id, org_id=org_id)

        raw_key = generate_api_key()
        hashed = hash_api_key(raw_key)
        prefix = key_prefix(raw_key)

        api_key = await self._repo.create_api_key(
            org_id=org_id,
            project_id=project_id,
            key_hash=hashed,
            key_prefix=prefix,
            name=name,
            created_by=created_by,
        )
        return api_key, raw_key

    async def list_api_keys(self, org_id: UUID) -> list[APIKey]:
        """List all API keys for an organisation."""
        await self.get_organization(org_id)
        return await self._repo.list_api_keys(org_id)

    async def list_project_api_keys(self, project_id: UUID) -> list[APIKey]:
        """List all API keys for a specific project."""
        return await self._repo.list_project_api_keys(project_id)

    async def revoke_api_key(self, key_id: UUID, *, org_id: UUID) -> None:
        """Deactivate an API key after verifying it belongs to *org_id*."""
        api_key = await self._repo.get_api_key(key_id)
        if api_key is None:
            raise NotFoundError(f"API key {key_id} not found.")
        if api_key.org_id != org_id:
            raise AuthorizationError("API key does not belong to this organisation.")
        await self._repo.revoke_api_key(key_id)
