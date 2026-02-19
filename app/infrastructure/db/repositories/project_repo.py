"""PostgreSQL repository for Projects."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import Project
from app.infrastructure.db.models import ProjectModel


class ProjectRepository:
    """Handles project persistence and lookups."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def create_project(self, org_id: UUID, name: str, description: str = "") -> Project:
        """Insert a new project row and return the domain entity."""
        row = ProjectModel(org_id=org_id, name=name, description=description)
        self._session.add(row)
        await self._session.flush()
        return self._to_entity(row)

    async def get_project(self, project_id: UUID) -> Project | None:
        """Fetch a project by primary key."""
        row = await self._session.get(ProjectModel, project_id)
        return self._to_entity(row) if row else None

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
