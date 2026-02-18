"""V1 API router that mounts all sub-routers under /v1."""

from fastapi import APIRouter

from app.api.v1.routes import auth, evaluations, health, organizations, projects, traces

v1_router = APIRouter()

v1_router.include_router(auth.router)
v1_router.include_router(organizations.router)
v1_router.include_router(projects.router)
v1_router.include_router(traces.router)
v1_router.include_router(evaluations.router)
v1_router.include_router(health.router)
