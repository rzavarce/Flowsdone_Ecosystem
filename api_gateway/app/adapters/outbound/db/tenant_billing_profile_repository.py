"""SQLAlchemy implementation of TenantBillingProfileRepositoryPort."""

from __future__ import annotations

import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.models import TenantBillingProfileModel
from app.domain.models.tenant_billing_profile import TenantBillingProfile
from app.domain.ports.outbound import TenantBillingProfileRepositoryPort


def _to_domain(model: TenantBillingProfileModel) -> TenantBillingProfile:
    """Convert a TenantBillingProfileModel row into a domain object.

    Args:
        model (TenantBillingProfileModel): The ORM row to convert.

    Returns:
        TenantBillingProfile: The equivalent domain object.
    """
    return TenantBillingProfile(
        id=model.id,
        tenant_id=model.tenant_id,
        legal_name=model.legal_name,
        tax_id=model.tax_id,
        billing_email=model.billing_email,
        billing_contact_name=model.billing_contact_name,
        billing_phone=model.billing_phone,
        address_line1=model.address_line1,
        address_line2=model.address_line2,
        city=model.city,
        state_province=model.state_province,
        postal_code=model.postal_code,
        country=model.country,
        currency=model.currency,
        plan=model.plan,
        billing_cycle=model.billing_cycle,
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyTenantBillingProfileRepository(TenantBillingProfileRepositoryPort):
    """Postgres-backed implementation of TenantBillingProfileRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def get_by_tenant_id(self, tenant_id: UUID) -> Optional[TenantBillingProfile]:
        """Fetch a tenant's billing profile.

        Args:
            tenant_id (UUID): The tenant.

        Returns:
            Optional[TenantBillingProfile]: The profile, or None if the
            tenant doesn't have one yet.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(TenantBillingProfileModel).where(TenantBillingProfileModel.tenant_id == tenant_id)
            )
            model = result.scalar_one_or_none()
            return _to_domain(model) if model else None

    async def upsert(self, tenant_id: UUID, **fields: object) -> TenantBillingProfile:
        """Create or update a tenant's billing profile.

        Args:
            tenant_id (UUID): The tenant.
            **fields (object): Fields to set; `None` values are ignored on
                an update (leave unset), and simply absent on a create.

        Returns:
            TenantBillingProfile: The resulting profile.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(TenantBillingProfileModel).where(TenantBillingProfileModel.tenant_id == tenant_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                model = TenantBillingProfileModel(
                    id=uuid.uuid4(), tenant_id=tenant_id, **{k: v for k, v in fields.items() if v is not None}
                )
                session.add(model)
            else:
                for key, value in fields.items():
                    if value is not None:
                        setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)
