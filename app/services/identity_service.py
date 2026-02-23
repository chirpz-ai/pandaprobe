"""Orchestration logic for the Identity domain.

Coordinates between API key generation, persistence, and domain
validation for organizations, memberships, projects, and API keys.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import APIKey, Membership, Organization, Project
from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.infrastructure.db.repositories.project_repo import ProjectRepository
from app.registry.constants import MembershipRole
from app.registry.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.registry.security import generate_api_key, hash_api_key, key_prefix


class IdentityService:
    """Application service that manages organizations, memberships, and API keys."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._repo = IdentityRepository(session)
        self._project_repo = ProjectRepository(session)

    # -- organization ---------------------------------------------------------

    async def create_organization(self, name: str, owner_id: UUID) -> Organization:
        """Create a new tenant organization and assign the owner membership."""
        if not name or not name.strip():
            raise ValidationError("Organization name must not be empty.")

        org = await self._repo.create_organization(name=name.strip())
        await self._repo.create_membership(user_id=owner_id, org_id=org.id, role=MembershipRole.OWNER)
        return org

    async def get_organization(self, org_id: UUID) -> Organization:
        """Retrieve an organization or raise ``NotFoundError``."""
        org = await self._repo.get_organization(org_id)
        if org is None:
            raise NotFoundError(f"Organization {org_id} not found.")
        return org

    async def update_organization(self, org_id: UUID, *, name: str | None = None) -> Organization:
        """Update mutable organization fields."""
        final_name = name.strip() if name is not None else None
        if final_name is not None and not final_name:
            raise ValidationError("Organization name must not be empty.")
        org = await self._repo.update_organization(org_id, name=final_name)
        if org is None:
            raise NotFoundError(f"Organization {org_id} not found.")
        return org

    async def delete_organization(self, org_id: UUID) -> None:
        """Hard-delete an organization and all related data (CASCADE)."""
        await self.get_organization(org_id)
        await self._repo.delete_organization(org_id)

    # -- Membership -----------------------------------------------------------

    async def require_membership(self, user_id: UUID, org_id: UUID) -> Membership:
        """Ensure the user belongs to the org, or raise ``AuthorizationError``."""
        membership = await self._repo.get_membership(user_id, org_id)
        if membership is None:
            raise AuthorizationError("You are not a member of this organization.")
        return membership

    async def require_admin(self, user_id: UUID, org_id: UUID) -> Membership:
        """Ensure the user is at least ADMIN in the org."""
        m = await self.require_membership(user_id, org_id)
        if m.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
            raise AuthorizationError("Admin or Owner role required.")
        return m

    async def require_owner(self, user_id: UUID, org_id: UUID) -> Membership:
        """Ensure the user is OWNER in the org."""
        m = await self.require_membership(user_id, org_id)
        if m.role != MembershipRole.OWNER:
            raise AuthorizationError("Owner role required.")
        return m

    async def add_member(
        self,
        actor_id: UUID,
        org_id: UUID,
        user_id: UUID,
        role: MembershipRole = MembershipRole.MEMBER,
    ) -> Membership:
        """Add a user to an organization, respecting role hierarchy.

        - OWNER can add with any role (OWNER, ADMIN, MEMBER).
        - ADMIN can add with MEMBER role only.
        - MEMBER cannot add anyone.
        """
        actor = await self.require_membership(actor_id, org_id)

        if actor.role == MembershipRole.MEMBER:
            raise AuthorizationError("Members cannot add users to the organization.")

        if actor.role == MembershipRole.ADMIN and role != MembershipRole.MEMBER:
            raise AuthorizationError("Admins can only add users with MEMBER role.")

        existing = await self._repo.get_membership(user_id, org_id)
        if existing:
            raise ConflictError("User is already a member of this organization.")
        return await self._repo.create_membership(user_id=user_id, org_id=org_id, role=role)

    async def update_member_role(
        self, actor_id: UUID, org_id: UUID, target_user_id: UUID, new_role: MembershipRole
    ) -> Membership:
        """Change a member's role, respecting hierarchy.

        - Cannot change your own role.
        - OWNER can change any non-OWNER to any role (including OWNER).
        - ADMIN and MEMBER cannot change roles.
        """
        if actor_id == target_user_id:
            raise AuthorizationError("Cannot change your own role.")

        actor = await self.require_membership(actor_id, org_id)
        if actor.role != MembershipRole.OWNER:
            raise AuthorizationError("Only owners can change member roles.")

        target = await self._repo.get_membership(target_user_id, org_id)
        if target is None:
            raise NotFoundError("Target user is not a member of this organization.")

        if target.role == MembershipRole.OWNER:
            raise AuthorizationError("Cannot change the role of another owner.")

        updated = await self._repo.update_membership_role(target_user_id, org_id, new_role)
        if updated is None:
            raise NotFoundError("Target user is not a member of this organization.")
        return updated

    async def remove_member(self, actor_id: UUID, org_id: UUID, target_user_id: UUID) -> None:
        """Remove a member from an organization, respecting role hierarchy.

        - OWNER can remove ADMIN and MEMBER (not other OWNERs).
        - ADMIN can remove MEMBER only.
        - MEMBER cannot remove anyone.
        """
        actor = await self.require_membership(actor_id, org_id)
        target = await self._repo.get_membership(target_user_id, org_id)
        if target is None:
            raise NotFoundError("Target user is not a member of this organization.")

        if target.role == MembershipRole.OWNER:
            raise AuthorizationError("Cannot remove an OWNER from the organization.")

        if actor.role == MembershipRole.MEMBER:
            raise AuthorizationError("Members cannot remove other members.")

        if actor.role == MembershipRole.ADMIN and target.role != MembershipRole.MEMBER:
            raise AuthorizationError("Admins can only remove members with MEMBER role.")

        await self._repo.delete_membership(target_user_id, org_id)

    async def list_user_orgs(self, user_id: UUID) -> list[Membership]:
        """Return all memberships for a user."""
        return await self._repo.list_user_orgs(user_id)

    async def list_org_members(self, org_id: UUID) -> list[Membership]:
        """Return all members of an organization."""
        return await self._repo.list_org_members(org_id)

    # -- Project --------------------------------------------------------------

    async def create_project(self, org_id: UUID, name: str, description: str = "") -> Project:
        """Create a new project within an organization."""
        await self.get_organization(org_id)
        return await self._project_repo.create_project(org_id=org_id, name=name, description=description)

    async def get_project(self, project_id: UUID, *, org_id: UUID | None = None) -> Project:
        """Fetch a project or raise ``NotFoundError``.

        When *org_id* is supplied the project must belong to that
        organization, otherwise ``AuthorizationError`` is raised.
        """
        project = await self._project_repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.")
        if org_id is not None and project.org_id != org_id:
            raise AuthorizationError("Project does not belong to this organization.")
        return project

    async def update_project(
        self,
        org_id: UUID,
        project_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update a project's name and/or description."""
        project = await self.get_project(project_id, org_id=org_id)
        final_name = name.strip() if name is not None else None
        if final_name is not None and not final_name:
            raise ValidationError("Project name must not be empty.")
        updated = await self._project_repo.update_project(
            project.id, name=final_name, description=description,
        )
        if updated is None:
            raise NotFoundError(f"Project {project_id} not found.")
        return updated

    async def delete_project(self, org_id: UUID, project_id: UUID) -> None:
        """Delete a project and all associated data (traces, evaluations).

        PostgreSQL ``ON DELETE CASCADE`` handles child records.
        """
        await self.get_project(project_id, org_id=org_id)
        await self._project_repo.delete_project(project_id)

    async def list_projects(self, org_id: UUID) -> list[Project]:
        """List all projects for an organization."""
        return await self._project_repo.list_projects(org_id)

    # -- API Keys -------------------------------------------------------------

    _EXPIRATION_DELTAS: dict[str, timedelta | None] = {
        "never": None,
        "90d": timedelta(days=90),
    }

    async def create_api_key(
        self,
        org_id: UUID,
        name: str,
        created_by: UUID | None = None,
        expiration: str = "never",
    ) -> tuple[APIKey, str]:
        """Generate a new org-scoped API key.

        Args:
            expiration: ``"never"`` (no expiry, default) or ``"90d"`` (90-day TTL).

        Returns:
            A tuple of (APIKey entity, raw_key_string).
        """
        await self.get_organization(org_id)

        if expiration not in self._EXPIRATION_DELTAS:
            raise ValidationError(
                f"Unsupported expiration value '{expiration}'. "
                f"Allowed: {', '.join(sorted(self._EXPIRATION_DELTAS))}."
            )
        delta = self._EXPIRATION_DELTAS[expiration]
        expires_at: datetime | None = datetime.now(timezone.utc) + delta if delta else None

        raw_key = generate_api_key()
        hashed = hash_api_key(raw_key)
        prefix = key_prefix(raw_key)

        api_key = await self._repo.create_api_key(
            org_id=org_id,
            key_hash=hashed,
            key_prefix=prefix,
            name=name,
            created_by=created_by,
            expires_at=expires_at,
        )
        return api_key, raw_key

    async def get_api_key(self, key_id: UUID, *, org_id: UUID) -> APIKey:
        """Fetch a single API key, verifying it belongs to *org_id*."""
        api_key = await self._repo.get_api_key(key_id)
        if api_key is None:
            raise NotFoundError(f"API key {key_id} not found.")
        if api_key.org_id != org_id:
            raise AuthorizationError("API key does not belong to this organization.")
        return api_key

    async def list_api_keys(self, org_id: UUID) -> list[APIKey]:
        """List all API keys for an organization."""
        await self.get_organization(org_id)
        return await self._repo.list_api_keys(org_id)

    async def rotate_api_key(
        self, key_id: UUID, *, org_id: UUID, created_by: UUID | None = None,
    ) -> tuple[APIKey, str]:
        """Create a replacement key with a fresh 90-day expiration.

        The old key remains active until its original expiration.
        Only keys that have an expiration date can be rotated.
        """
        old_key = await self.get_api_key(key_id, org_id=org_id)
        if old_key.expires_at is None:
            raise ValidationError(
                "Only keys with an expiration can be rotated. "
                "Production keys (never expire) should be revoked and re-created instead."
            )

        return await self.create_api_key(
            org_id=org_id,
            name=old_key.name,
            created_by=created_by,
            expiration="90d",
        )

    async def revoke_api_key(self, key_id: UUID, *, org_id: UUID) -> None:
        """Deactivate an API key after verifying it belongs to *org_id*."""
        await self.get_api_key(key_id, org_id=org_id)
        await self._repo.revoke_api_key(key_id)
