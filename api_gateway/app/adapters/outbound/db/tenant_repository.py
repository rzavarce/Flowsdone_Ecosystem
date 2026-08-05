"""SQLAlchemy implementation of TenantRepositoryPort."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.tenant import Tenant
from ....domain.ports.outbound import TenantRepositoryPort
from .models import TenantModel


def _to_domain(model: TenantModel) -> Tenant:
    """Convert a TenantModel row into a Tenant domain object.

    Args:
        model (TenantModel): The ORM row to convert.

    Returns:
        Tenant: The equivalent domain object.
    """
    return Tenant(
        id=model.id,
        name=model.name,
        slug=model.slug,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyTenantRepository(TenantRepositoryPort):
    """Postgres-backed implementation of TenantRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def create(self, *, name: str, slug: str) -> Tenant:
        """Insert a new tenant row.

        Args:
            name (str): Display name of the tenant.
            slug (str): Unique URL-safe identifier for the tenant.

        Returns:
            Tenant: The created tenant.
        """
        async with self._sessionmaker() as session:
            model = TenantModel(name=name, slug=slug)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Fetch a tenant by id.

        Args:
            tenant_id (UUID): Id of the tenant.

        Returns:
            Optional[Tenant]: The tenant, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(TenantModel, tenant_id)
            return _to_domain(model) if model else None

    async def list(self) -> List[Tenant]:
        """List all tenants, ordered by creation date.

        Returns:
            List[Tenant]: All existing tenants.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(select(TenantModel).order_by(TenantModel.created_at))
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, tenant_id: UUID, **fields: Any) -> Optional[Tenant]:
        """Update a tenant's fields.

        Args:
            tenant_id (UUID): Id of the tenant to update.
            **fields (Any): Fields to update; None values are ignored.

        Returns:
            Optional[Tenant]: The updated tenant, or None if it does
            not exist.
        """
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
        """Delete a tenant.

        Args:
            tenant_id (UUID): Id of the tenant to delete.

        Returns:
            bool: True if a tenant was deleted, False if it did not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(TenantModel, tenant_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
