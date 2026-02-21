"""Health-check routes.

These endpoints are unauthenticated and used by load-balancers,
Docker health-checks, and monitoring probes.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.registry.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Return service health status and version metadata.

    Auth: `public`
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.APP_ENV.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
