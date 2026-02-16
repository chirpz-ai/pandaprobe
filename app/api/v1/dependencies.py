"""FastAPI dependency functions for authentication and database access.

``require_org`` resolves the calling organisation from the
``X-API-Key`` request header and is injected into every
authenticated route.
"""

from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import Organization
from app.infrastructure.db.engine import get_db_session
from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.registry.exceptions import AuthenticationError
from app.registry.security import hash_api_key


async def require_org(
    x_api_key: str = Header(..., alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> Organization:
    """Validate the API key header and return the owning Organisation.

    Raises:
        AuthenticationError: If the key is missing, invalid, or revoked.
    """
    key_hash = hash_api_key(x_api_key)
    repo = IdentityRepository(session)

    api_key = await repo.get_api_key_by_hash(key_hash)
    if api_key is None:
        raise AuthenticationError()

    # Stamp last-used (fire-and-forget within the same transaction).
    await repo.touch_api_key(api_key.id)

    org = await repo.get_organization(api_key.org_id)
    if org is None:
        raise AuthenticationError("Organisation for this key no longer exists.")

    return org
