"""V1 API router that mounts all sub-routers."""

from fastapi import APIRouter

from app.api.v1.routes import (
    api_keys,
    evaluations,
    health,
    organizations,
    projects,
    sessions,
    subscriptions,
    traces,
    user,
    webhooks,
)

v1_router = APIRouter()

v1_router.include_router(health.router)
v1_router.include_router(user.router)
v1_router.include_router(organizations.router)
v1_router.include_router(subscriptions.router)
v1_router.include_router(projects.router)
v1_router.include_router(api_keys.router)
v1_router.include_router(traces.router)
v1_router.include_router(sessions.router)
v1_router.include_router(evaluations.router)
v1_router.include_router(webhooks.router)
