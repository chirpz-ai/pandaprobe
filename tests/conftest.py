"""Shared test fixtures.

Sets Celery to eager mode so tasks execute synchronously during tests,
and provides a configured ``httpx.AsyncClient`` bound to the FastAPI app.
"""

import os

# Force test settings before anything else is imported.
os.environ["APP_ENV"] = "test"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_HOST"] = "localhost"
os.environ["AUTH_PROVIDER"] = "supabase"

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """Yield an async test client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
