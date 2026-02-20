"""Unified request context — the single source of truth for every API call."""

from enum import StrEnum

import structlog
from pydantic import BaseModel, ConfigDict

from app.core.identity.entities import Organization, Project, User


class AuthMethod(StrEnum):
    """How the caller authenticated."""

    JWT = "JWT"
    API_KEY = "API_KEY"


class ApiContext(BaseModel):
    """Immutable bag of resolved identity and request metadata.

    Built once per request by ``get_api_context`` and injected into
    every route handler via ``Depends``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    request_id: str
    auth_method: AuthMethod
    organization: Organization
    project: Project | None = None
    user: User | None = None
    logger: structlog.stdlib.BoundLogger
