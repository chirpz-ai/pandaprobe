"""Routes for the CLI OAuth2 Authorization Code + PKCE login flow.

Two endpoints implement the ``pandaprobe auth login`` contract:

- ``POST /cli/auth/codes`` (B1) — issue a single-use authorization code.
  Authenticated as the Firebase user (Bearer JWT); called by the web
  ``/cli-login`` consent page.
- ``POST /cli/auth/exchange`` (B2) — exchange the code + PKCE verifier
  for a 90-day API key. **No auth header** (the code + verifier is the
  proof); rate-limited.

These paths are part of the CLI's compiled-in contract — do not rename.
"""

from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.api.rate_limit import limiter
from app.infrastructure.db.engine import get_db_session
from app.infrastructure.redis.client import get_redis
from app.registry.exceptions import AuthenticationError
from app.services.analytics_service import AnalyticsService
from app.services.cli_service import CliAuthService

router = APIRouter(prefix="/cli/auth", tags=["cli-auth"])


def _require_user(ctx: ApiContext) -> None:
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IssueCodeRequest(BaseModel):
    """Payload for issuing a single-use CLI authorization code."""

    org_id: UUID
    project_id: UUID
    code_challenge: str = Field(min_length=1, description="BASE64URL(SHA256(code_verifier)) from the CLI")
    code_challenge_method: str = Field(default="S256", description="Always 'S256'")
    label: str = Field(min_length=1, max_length=255, description="Human label (the dev's hostname)")
    expires_days: int = Field(default=90, description="Key lifetime in days; only 90 is supported")


class IssueCodeResponse(BaseModel):
    """Single-use code for the PKCE exchange."""

    code: str
    expires_in: int


class ExchangeRequest(BaseModel):
    """Payload for exchanging a code + PKCE verifier for an API key."""

    code: str = Field(min_length=1)
    code_verifier: str = Field(min_length=1)


class ExchangeResponse(BaseModel):
    """Minted 90-day API key bundle — the raw key is shown exactly once."""

    api_key: str
    project_name: str
    org_id: str
    key_id: str
    key_prefix: str
    expires_at: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/codes", status_code=201, response_model=IssueCodeResponse)
async def issue_cli_code(
    body: IssueCodeRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> IssueCodeResponse:
    """Issue a short-lived, single-use authorization code for the CLI.

    Auth: `Bearer`

    Binds the code to ``{user, org, project, code_challenge}`` in Redis
    with a ~120s TTL. **No API key is created here** — the key is minted
    only at exchange time.
    """
    _require_user(ctx)
    svc = CliAuthService(redis_client, session)
    code, expires_in = await svc.issue_code(
        user_id=ctx.user.id,
        org_id=body.org_id,
        project_id=body.project_id,
        code_challenge=body.code_challenge,
        code_challenge_method=body.code_challenge_method,
        label=body.label,
        expires_days=body.expires_days,
    )
    return IssueCodeResponse(code=code, expires_in=expires_in)


@router.post("/exchange", response_model=ExchangeResponse)
@limiter.limit("20/minute")
async def exchange_cli_code(
    request: Request,
    body: ExchangeRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> ExchangeResponse:
    """Exchange a single-use code + PKCE verifier for a 90-day API key.

    Auth: **none** — the `code` + `code_verifier` is the proof.

    The code is consumed atomically (single-use) and the PKCE challenge
    is verified with a constant-time compare. The raw key is returned
    exactly once. Rate limit: `20/min`.
    """
    svc = CliAuthService(redis_client, session)
    result = await svc.exchange(code=body.code, code_verifier=body.code_verifier)
    user_id = result.pop("user_id")
    AnalyticsService().api_key_created(org_id=result["org_id"], user_id=user_id)
    return ExchangeResponse(**result)
