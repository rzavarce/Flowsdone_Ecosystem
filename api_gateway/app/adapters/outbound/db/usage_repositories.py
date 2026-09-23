"""SQLAlchemy implementations of CostRateRepositoryPort and
SyncCursorRepositoryPort."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.models import CostRateModel, SyncCursorModel
from app.domain.models.usage import CostRate
from app.domain.ports.outbound import CostRateRepositoryPort, SyncCursorRepositoryPort

_RATE_FIELDS = (
    "id",
    "kind",
    "provider",
    "sku",
    "unit",
    "price_micros",
    "per_quantity",
    "currency",
    "valid_from",
    "note",
    "created_at",
)


def _to_rate(model: CostRateModel) -> CostRate:
    """Convert a CostRateModel row into a domain object.

    Args:
        model (CostRateModel): The ORM row.

    Returns:
        CostRate: The rate.
    """
    return CostRate(**{field: getattr(model, field) for field in _RATE_FIELDS})


class SqlAlchemyCostRateRepository(CostRateRepositoryPort):
    """Postgres-backed cost catalog."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def list_all(self) -> List[CostRate]:
        """Every rate, newest valid_from first.

        Returns:
            List[CostRate]: All rates.
        """
        async with self._sessionmaker() as session:
            rows = (
                await session.execute(
                    select(CostRateModel).order_by(
                        CostRateModel.kind, CostRateModel.provider, CostRateModel.sku, CostRateModel.valid_from.desc()
                    )
                )
            ).scalars()
            return [_to_rate(row) for row in rows]

    async def create(self, rate: CostRate) -> CostRate:
        """Store a new rate.

        Args:
            rate (CostRate): The rate.

        Returns:
            CostRate: The stored rate (with created_at).
        """
        async with self._sessionmaker() as session:
            model = CostRateModel(**rate.model_dump(exclude={"created_at"}))
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_rate(model)

    async def delete(self, rate_id: UUID) -> bool:
        """Delete a rate.

        Args:
            rate_id (UUID): Rate id.

        Returns:
            bool: True if it existed.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(delete(CostRateModel).where(CostRateModel.id == rate_id))
            await session.commit()
            return result.rowcount > 0


class SqlAlchemySyncCursorRepository(SyncCursorRepositoryPort):
    """Postgres-backed sync cursors."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def get(self, name: str) -> Optional[datetime]:
        """Read a cursor.

        Args:
            name (str): Cursor name.

        Returns:
            Optional[datetime]: Its position, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(SyncCursorModel, name)
            return model.position if model else None

    async def set(self, name: str, position: datetime) -> None:
        """Create or move a cursor.

        Args:
            name (str): Cursor name.
            position (datetime): New position.
        """
        statement = (
            insert(SyncCursorModel)
            .values(name=name, position=position)
            .on_conflict_do_update(index_elements=["name"], set_={"position": position})
        )
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()
