from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.tenant import Tenant
from ....domain.ports.outbound import TenantRepositoryPort
from .models import TenantModel


def _to_domain(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        name=model.name,
        slug=model.slug,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyTenantRepository(TenantRepositoryPort):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def create(self, *, name: str, slug: str) -> Tenant:
        async with self._sessionmaker() as session:
            model = TenantModel(name=name, slug=slug)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        async with self._sessionmaker() as session:
            model = await session.get(TenantModel, tenant_id)
            return _to_domain(model) if model else None

    async def list(self) -> List[Tenant]:
        async with self._sessionmaker() as session:
            result = await session.execute(select(TenantModel).order_by(TenantModel.created_at))
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, tenant_id: UUID, **fields: Any) -> Optional[Tenant]:
        async with self._sessionmaker() as session:
            model = await session.get(TenantModel, tenant_id)
            if not model:
                return None
            for key, value in fields.items():
                if value is not None:
                    setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def delete(self, tenant_id: UUID) -> bool:
        async with self._sessionmaker() as session:
            model = await session.get(TenantModel, tenant_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
