"""Routes for managing projects within an organization.

All endpoints require a valid app JWT via the ``X-Auth-Token`` header
and verify the caller's membership in the target organization.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.identity.entities import User
from app.infrastructure.db.engine import get_db_session
from app.services.identity_service import IdentityService

router = APIRouter(prefix="/organizations/{org_id}/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Payload for creating a new project."""

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class ProjectResponse(BaseModel):
    """Public representation of a project."""

    id: UUID
    org_id: UUID
    name: str
    description: str
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(
    org_id: UUID,
    body: CreateProjectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Create a new project within the organization."""
    svc = IdentityService(session)
    await svc.require_membership(user.id, org_id)
    project = await svc.create_project(org_id=org_id, name=body.name, description=body.description)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    org_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectResponse]:
    """List all projects for the organization."""
    svc = IdentityService(session)
    await svc.require_membership(user.id, org_id)
    projects = await svc.list_projects(org_id)
    return [
        ProjectResponse(
            id=p.id,
            org_id=p.org_id,
            name=p.name,
            description=p.description,
            created_at=p.created_at.isoformat(),
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    org_id: UUID,
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Retrieve a single project."""
    svc = IdentityService(session)
    await svc.require_membership(user.id, org_id)
    project = await svc.get_project(project_id, org_id=org_id)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
    )
