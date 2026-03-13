"""Integration test fixtures: real database, real Redis, real Celery (eager).

The test stack mirrors dev/prod as closely as possible:
- **PostgreSQL** on port 5433 (``docker-compose.test.yml``)
- **Redis** on port 6380 for the rate limiter and Celery broker
- **Celery eager mode** (``CELERY_TASK_ALWAYS_EAGER=true``) so tasks run
  in-process through the full Celery machinery (serialisation, retry
  logic, etc.) without a separate worker process.

``nest_asyncio`` patches the event loop to be re-entrant so that the
Celery task's ``asyncio.run(_persist_trace(...))`` works inside the
already-running pytest-asyncio event loop.  The task opens its **own**
DB session (just like a real worker would) and commits independently.
Subsequent GET requests see that committed data thanks to PostgreSQL's
READ COMMITTED isolation.

Per-test isolation is achieved via TRUNCATE — not transaction rollback —
because asyncpg forbids concurrent operations on a single connection
and the Celery task creates its own session anyway.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import UUID

import nest_asyncio
import pytest
import structlog
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext, AuthMethod
from app.api.dependencies import require_project
from app.core.identity.entities import Organization, Project
from app.core.traces.entities import Span, Trace
from app.infrastructure.db.engine import async_session_factory, engine as async_engine, get_db_session
from app.infrastructure.db.models import Base, OrganizationModel, ProjectModel
from app.infrastructure.db.repositories.trace_repo import TraceRepository
from app.main import app
from app.registry.constants import SpanKind, SpanStatusCode, TraceStatus
from app.registry.settings import settings

from .factories import build_trace_payload

# Allow asyncio.run() inside an already-running loop (needed by Celery eager).
nest_asyncio.apply()

# Fixed UUIDs so every fixture in the same test shares the same identity.
TEST_ORG_ID = UUID("00000000-0000-4000-a000-000000000001")
TEST_PROJECT_ID = UUID("00000000-0000-4000-a000-000000000002")


# ---------------------------------------------------------------------------
# Session-scoped: create / drop all tables once per test run (sync to avoid
# event-loop mismatch between session-scoped and function-scoped fixtures).
# ---------------------------------------------------------------------------

_sync_engine = create_engine(settings.DATABASE_URL_SYNC)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all ORM tables at session start, drop them at teardown."""
    Base.metadata.create_all(bind=_sync_engine)
    yield
    Base.metadata.drop_all(bind=_sync_engine)
    _sync_engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped: per-test session with TRUNCATE cleanup
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session with pre-seeded org/project, cleaned up after the test."""
    session = async_session_factory()

    now = datetime.now(timezone.utc)
    session.add(OrganizationModel(id=TEST_ORG_ID, name="Test Org", created_at=now))
    session.add(
        ProjectModel(
            id=TEST_PROJECT_ID,
            org_id=TEST_ORG_ID,
            name="Test Project",
            description="",
            created_at=now,
        )
    )
    await session.commit()

    yield session

    # Remove all data while preserving the schema.
    await session.execute(
        text("TRUNCATE eval_monitors, session_scores, trace_scores, eval_runs, spans, traces, api_keys, memberships, projects, organizations CASCADE")
    )
    await session.commit()
    await session.close()
    # Dispose the async engine's pool so pooled connections don't leak
    # into the next test's event loop (pytest-asyncio creates a new loop
    # per test function by default).
    await async_engine.dispose()


# ---------------------------------------------------------------------------
# Domain entity helpers (used by dependency overrides and tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_org() -> Organization:
    """Return the domain entity matching the seeded organization."""
    return Organization(
        id=TEST_ORG_ID,
        name="Test Org",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_project() -> Project:
    """Return the domain entity matching the seeded project."""
    return Project(
        id=TEST_PROJECT_ID,
        org_id=TEST_ORG_ID,
        name="Test Project",
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# FastAPI dependency overrides (autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _override_deps(
    db_session: AsyncSession,
    test_org: Organization,
    test_project: Project,
):
    """Replace auth and DB session dependencies for every integration test.

    ``get_db_session`` is overridden so that route handlers (GET, PATCH,
    DELETE, list, analytics) use the same session as the test code.
    The Celery task is NOT affected — it creates its own session via
    ``async_session_factory()`` just like a real worker, and commits
    independently.
    """

    async def _get_db_session() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    def _require_project() -> ApiContext:
        return ApiContext.model_construct(
            request_id="test-request",
            auth_method=AuthMethod.API_KEY,
            organization=test_org,
            project=test_project,
            user=None,
            logger=structlog.get_logger(),
        )

    app.dependency_overrides[get_db_session] = _get_db_session
    app.dependency_overrides[require_project] = _require_project
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Data-seeding helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_trace(db_session: AsyncSession):
    """Factory fixture: insert a trace directly into the test database.

    Returns an async callable that accepts the same keyword overrides as
    ``build_trace_payload`` and returns the persisted ``Trace`` entity.
    Useful for seeding data in read/update/delete tests without going
    through the POST /traces -> Celery path.
    """

    async def _seed(**overrides) -> Trace:
        payload = build_trace_payload(**overrides)
        trace_id = payload.pop("trace_id")
        spans_raw = payload.pop("spans", [])
        spans = [
            Span(
                span_id=s["span_id"],
                trace_id=trace_id,
                parent_span_id=s.get("parent_span_id"),
                name=s["name"],
                kind=SpanKind(s.get("kind", "OTHER")),
                status=SpanStatusCode(s.get("status", "UNSET")),
                input=s.get("input"),
                output=s.get("output"),
                model=s.get("model"),
                token_usage=s.get("token_usage"),
                metadata=s.get("metadata", {}),
                started_at=s["started_at"],
                ended_at=s.get("ended_at"),
                error=s.get("error"),
                completion_start_time=s.get("completion_start_time"),
                model_parameters=s.get("model_parameters"),
                cost=s.get("cost"),
            )
            for s in spans_raw
        ]
        trace = Trace(
            trace_id=trace_id,
            project_id=TEST_PROJECT_ID,
            name=payload["name"],
            status=TraceStatus(payload.get("status", "COMPLETED")),
            input=payload.get("input"),
            output=payload.get("output"),
            metadata=payload.get("metadata", {}),
            started_at=payload["started_at"],
            ended_at=payload.get("ended_at"),
            session_id=payload.get("session_id"),
            user_id=payload.get("user_id"),
            tags=payload.get("tags", []),
            environment=payload.get("environment"),
            release=payload.get("release"),
            spans=spans,
        )
        repo = TraceRepository(db_session)
        persisted = await repo.upsert_trace(trace)
        await db_session.commit()
        return persisted

    return _seed
