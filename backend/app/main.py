"""FastAPI application entry point for PandaProbe."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.rate_limit import limiter
from app.api.v1.router import v1_router
from app.infrastructure.redis.client import close_redis_pool
from app.logging import logger
from app.registry.exceptions import PandaProbeError
from app.registry.settings import Environment, settings


def _validate_stripe_settings() -> None:
    """Fail fast if Stripe keys are missing in staging/production."""
    if settings.APP_ENV in (Environment.STAGING, Environment.PRODUCTION):
        missing = [name for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET") if not getattr(settings, name, "")]
        if missing:
            raise RuntimeError(
                f"Stripe configuration incomplete for {settings.APP_ENV.value}: missing {', '.join(missing)}"
            )


def _warn_auth_disabled() -> None:
    """Log a prominent warning when JWT authentication is turned off."""
    if not settings.AUTH_ENABLED:
        logger.warning(
            "auth_disabled",
            message="Authentication is DISABLED. All management routes are accessible without a JWT. "
            "This must only be used for local development.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown lifecycle events."""
    _validate_stripe_settings()
    _warn_auth_disabled()
    logger.info(
        "application_startup",
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.APP_ENV.value,
    )
    yield
    await close_redis_pool()
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter

# -- Middleware ---------------------------------------------------------------

app.add_middleware(RequestContextMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "X-API-Key",
        "X-Organization-ID",
        "X-Project-ID",
        "X-Project-Name",
        "X-Request-ID",
        "Content-Type",
        "Accept",
    ],
)

# -- Exception handlers -------------------------------------------------------

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(PandaProbeError)
async def domain_exception_handler(_request: Request, exc: PandaProbeError) -> JSONResponse:
    """Translate domain exceptions into structured JSON error responses."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return readable validation errors from Pydantic request parsing."""
    errors = [
        {
            "field": " -> ".join(str(p) for p in err["loc"] if p != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Validation error", "errors": errors},
    )


# -- Routers ------------------------------------------------------------------

app.include_router(v1_router)


@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    """Serve Scalar API reference documentation."""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=f"{settings.PROJECT_NAME} API Reference",
    )


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with basic API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "docs": "/docs",
        "scalar": "/scalar",
    }
