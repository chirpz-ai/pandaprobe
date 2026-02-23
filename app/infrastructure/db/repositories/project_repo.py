"""PostgreSQL repository for Projects."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import Project
from app.infrastructure.db.models import ProjectModel
from app.registry.exceptions import ConflictError


class ProjectRepository:
    """Handles project persistence and lookups."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def create_project(self, org_id: UUID, name: str, description: str = "") -> Project:
        """Insert a new project row and return the domain entity.

        Raises ``ConflictError`` if a project with the same name
        already exists in the organization.
        """
        row = ProjectModel(org_id=org_id, name=name, description=description)
        self._session.add(row)
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError:
            raise ConflictError(f"A project named '{name}' already exists in this organization.")
        return self._to_entity(row)

    async def get_project(self, project_id: UUID) -> Project | None:
        """Fetch a project by primary key."""
        row = await self._session.get(ProjectModel, project_id)
        return self._to_entity(row) if row else None

    async def get_project_by_name(self, org_id: UUID, name: str) -> Project | None:
        """Fetch a project by (org_id, name) pair. Returns ``None`` if not found."""
        stmt = select(ProjectModel).where(ProjectModel.org_id == org_id, ProjectModel.name == name)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_or_create_project(self, org_id: UUID, name: str) -> Project:
        """Resolve a project by name within an org, auto-creating it if missing.

        Uses a SAVEPOINT so that a unique-constraint race only rolls
        back the failed INSERT, not the entire transaction.
        """
        existing = await self.get_project_by_name(org_id, name)
        if existing:
            return existing
        row = ProjectModel(org_id=org_id, name=name)
        self._session.add(row)
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError:
            existing = await self.get_project_by_name(org_id, name)
            if existing:
                return existing
            raise
        return self._to_entity(row)

    async def update_project(
        self, project_id: UUID, *, name: str | None = None, description: str | None = None
    ) -> Project | None:
        """Update mutable project fields (name, description).

        Raises ``ConflictError`` if the new name collides with another
        project in the same organization.
        """
        row = await self._session.get(ProjectModel, project_id)
        if row is None:
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError:
            raise ConflictError(f"A project named '{name}' already exists in this organization.")
        return self._to_entity(row)

    async def delete_project(self, project_id: UUID) -> None:
        """Hard-delete a project (DB CASCADE removes traces and evaluations)."""
        row = await self._session.get(ProjectModel, project_id)
        if row:
            await self._session.delete(row)
            await self._session.flush()

    async def list_projects(self, org_id: UUID) -> list[Project]:
        """Return all projects for an organization."""
        stmt = select(ProjectModel).where(ProjectModel.org_id == org_id).order_by(ProjectModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows]

    @staticmethod
    def _to_entity(row: ProjectModel) -> Project:
        return Project(
            id=row.id,
            org_id=row.org_id,
            name=row.name,
            description=row.description,
            created_at=row.created_at,
        )
