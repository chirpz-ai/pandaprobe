"""Routes for managing projects within an organization.

All endpoints require a valid external IdP JWT via the
``Authorization: Bearer`` header and verify the caller's
membership in the target organization.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.infrastructure.db.engine import get_db_session
from app.registry.exceptions import AuthenticationError
from app.services.identity_service import IdentityService

router = APIRouter(prefix="/organizations/{org_id}/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Payload for creating a new project."""

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class UpdateProjectRequest(BaseModel):
    """Payload for updating a project. Only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    """Public representation of a project."""

    id: UUID
    org_id: UUID
    name: str
    description: str
    created_at: str


def _require_user(ctx: ApiContext) -> None:
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(
    org_id: UUID,
    body: CreateProjectRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Create a new project within the organization.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_admin(ctx.user.id, org_id)
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
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectResponse]:
    """List all projects for the organization.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
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
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Retrieve a single project.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
    project = await svc.get_project(project_id, org_id=org_id)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    org_id: UUID,
    project_id: UUID,
    body: UpdateProjectRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Update a project's name and/or description.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`

    The `project_id` is immutable (API keys are scoped to it).
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_admin(ctx.user.id, org_id)
    project = await svc.update_project(
        org_id, project_id, name=body.name, description=body.description,
    )
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    org_id: UUID,
    project_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Permanently delete a project and all associated data.

    Auth: `Bearer` · role: `OWNER`

    Cascade deletes: traces, spans, evaluations, evaluation results, and API keys.
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_owner(ctx.user.id, org_id)
    await svc.delete_project(org_id, project_id)
