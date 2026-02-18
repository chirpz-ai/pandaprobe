"""FastAPI dependency functions for authentication and database access.

Two authentication mechanisms coexist:

1. **User JWT** (``X-Auth-Token`` header) -- protects management APIs
   (organizations, projects, users).  The token is issued by the
   ``POST /v1/auth/login`` endpoint after external IdP validation.

2. **API Key** (``X-API-Key`` header) -- protects data-plane APIs
   (traces, evaluations).  Each key is scoped to a project.
"""

from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import User
from app.infrastructure.auth.jwt import decode_app_token
from app.infrastructure.db.engine import get_db_session
from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.registry.exceptions import AuthenticationError
from app.registry.security import hash_api_key


class APIKeyContext(BaseModel):
    """Resolved context from a validated API key."""

    org_id: UUID
    project_id: UUID
    api_key_id: UUID


async def get_current_user(
    x_auth_token: str = Header(..., alias="X-Auth-Token"),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Validate the app JWT from X-Auth-Token and return the User entity.

    Raises:
        AuthenticationError: If the token is missing, invalid, or the user is unknown.
    """
    payload = decode_app_token(x_auth_token)
    user_id = UUID(payload["sub"])

    repo = UserRepository(session)
    user = await repo.get_user(user_id)
    if user is None:
        raise AuthenticationError("User account not found.")
    return user


async def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyContext:
    """Validate the API key header and return the resolved project context.

    Raises:
        AuthenticationError: If the key is missing, invalid, or revoked.
    """
    key_hash = hash_api_key(x_api_key)
    repo = IdentityRepository(session)

    api_key = await repo.get_api_key_by_hash(key_hash)
    if api_key is None:
        raise AuthenticationError()

    await repo.touch_api_key(api_key.id)

    return APIKeyContext(
        org_id=api_key.org_id,
        project_id=api_key.project_id,
        api_key_id=api_key.id,
    )
