"""SQLAlchemy async engine/session factory helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api_gateway.app.core.config import settings


def create_engine() -> AsyncEngine:
    """Create the async SQLAlchemy engine for the admin database.

    Returns:
        AsyncEngine: A configured engine.

    Raises:
        RuntimeError: If DATABASE_URL_SQLALCHEMY is not configured.
    """
    if not settings.DATABASE_URL_SQLALCHEMY:
        raise RuntimeError("DATABASE_URL_SQLALCHEMY is not configured")

    return create_async_engine(settings.DATABASE_URL_SQLALCHEMY, echo=False, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the given engine.

    Args:
        engine (AsyncEngine): The engine to bind sessions to.

    Returns:
        async_sessionmaker[AsyncSession]: A factory producing
        AsyncSession instances.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
