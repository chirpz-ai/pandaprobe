"""Async SQLAlchemy engine and session factory.

A single ``async_sessionmaker`` is exposed as the application-wide
session factory.  FastAPI dependencies use ``get_db_session()`` to
obtain a per-request session that is automatically closed.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.registry.settings import settings

#: Retire pooled connections well before anything upstream can reap them. Cloud
#: Run reaches Cloud SQL through a VPC connector whose instances are recycled as
#: it scales, so an established socket can die without either end noticing.
_POOL_RECYCLE_S = 1800

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=_POOL_RECYCLE_S,
    echo=False,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped async session, rolling back on unhandled errors."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
