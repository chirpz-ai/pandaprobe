"""V1 API router that mounts all sub-routers under /v1."""

from fastapi import APIRouter

from app.api.v1.routes import health, organizations, traces

v1_router = APIRouter()

v1_router.include_router(health.router)
v1_router.include_router(organizations.router)
v1_router.include_router(traces.router)
