"""Routes for managing organisations and their API keys.

The ``POST /organizations`` endpoint is intentionally open (no auth)
so that new tenants can self-register.  All other endpoints require a
valid API key.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.engine import get_db_session
from app.services.identity_service import IdentityService

router = APIRouter(prefix="/organizations", tags=["organizations"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateOrganizationRequest(BaseModel):
    """Payload for creating a new organisation."""

    name: str = Field(min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    """Public representation of an organisation."""

    id: UUID
    name: str
    created_at: str


class CreateAPIKeyRequest(BaseModel):
    """Payload for generating a new API key."""

    name: str = Field(min_length=1, max_length=255, description="Human-readable label for the key")


class APIKeyResponse(BaseModel):
    """Returned after creating an API key -- includes the raw key once."""

    id: UUID
    org_id: UUID
    key_prefix: str
    name: str
    is_active: bool
    created_at: str
    raw_key: str | None = Field(
        default=None,
        description="The full API key. Shown only at creation time.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=OrganizationResponse)
async def create_organization(
    body: CreateOrganizationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Register a new tenant organisation."""
    svc = IdentityService(session)
    org = await svc.create_organization(name=body.name)
    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.post("/{org_id}/api-keys", status_code=201, response_model=APIKeyResponse)
async def create_api_key(
    org_id: UUID,
    body: CreateAPIKeyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyResponse:
    """Generate a new API key for an organisation.

    The raw key value is returned **only once** in the response body.
    Store it securely; it cannot be recovered later.
    """
    svc = IdentityService(session)
    api_key, raw_key = await svc.create_api_key(org_id=org_id, name=body.name)
    return APIKeyResponse(
        id=api_key.id,
        org_id=api_key.org_id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat(),
        raw_key=raw_key,
    )


@router.get("/{org_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    org_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[APIKeyResponse]:
    """List all API keys belonging to an organisation."""
    svc = IdentityService(session)
    keys = await svc.list_api_keys(org_id=org_id)
    return [
        APIKeyResponse(
            id=k.id,
            org_id=k.org_id,
            key_prefix=k.key_prefix,
            name=k.name,
            is_active=k.is_active,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete("/{org_id}/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    org_id: UUID,
    key_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Revoke (soft-delete) an API key."""
    svc = IdentityService(session)
    await svc.revoke_api_key(key_id=key_id)
