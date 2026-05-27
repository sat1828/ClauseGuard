"""
ClauseGuard Database Layer
===========================
Async SQLAlchemy engine + session factory.

Design decisions:
- asyncpg driver for true async I/O (not thread-pool pseudo-async)
- NullPool in tests to avoid cross-test connection leaks
- Single session factory pattern — never create engines ad-hoc
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    Using declarative_base from DeclarativeBase (SQLAlchemy 2.x style).
    """
    pass


# Engine is module-level singleton — do not create per-request.
# pool_pre_ping=True reconnects on stale connections (important for Railway/cloud).
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=settings.DEBUG,  # SQL logging only in dev
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy-loading errors after commit in async
    autocommit=False,
    autoflush=False,
)


async def create_tables() -> None:
    """
    Create all tables from ORM models.
    Called on startup in non-production environments.
    Production uses Alembic migrations only.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_created")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
    Session is closed and rolled back on exception.

    Usage in router:
        async def endpoint(db: AsyncSession = Depends(get_session)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager version for use outside FastAPI request context.
    Used in background tasks and the analysis pipeline.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
