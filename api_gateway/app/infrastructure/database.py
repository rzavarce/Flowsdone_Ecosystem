from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..core.config import settings


def create_engine() -> AsyncEngine:
    if not settings.DATABASE_URL_SQLALCHEMY:
        raise RuntimeError("DATABASE_URL_SQLALCHEMY is not configured")

    return create_async_engine(settings.DATABASE_URL_SQLALCHEMY, echo=False, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
