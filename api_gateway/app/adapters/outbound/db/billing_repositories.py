"""SQLAlchemy implementations of the plan, subscription and statement
repositories."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.errors import duplicate_as_already_exists
from app.adapters.outbound.db.models import PlanModel, TenantSubscriptionModel, UsageStatementModel
from app.domain.models.billing import BillingStatement, Plan, TenantSubscription
from app.domain.ports.outbound import (
    PlanInUseError,
    PlanRepositoryPort,
    StatementRepositoryPort,
    SubscriptionRepositoryPort,
)

_PLAN_FIELDS = tuple(Plan.model_fields)
_SUBSCRIPTION_FIELDS = tuple(TenantSubscription.model_fields)


def _to_plan(model: PlanModel) -> Plan:
    """Convert a PlanModel row into a Plan.

    Args:
        model (PlanModel): The ORM row.

    Returns:
        Plan: The plan.
    """
    return Plan(**{field: getattr(model, field) for field in _PLAN_FIELDS})


def _to_subscription(model: TenantSubscriptionModel) -> TenantSubscription:
    """Convert a TenantSubscriptionModel row into a TenantSubscription.

    Args:
        model (TenantSubscriptionModel): The ORM row.

    Returns:
        TenantSubscription: The subscription.
    """
    return TenantSubscription(**{field: getattr(model, field) for field in _SUBSCRIPTION_FIELDS})


class SqlAlchemyPlanRepository(PlanRepositoryPort):
    """Postgres-backed plans."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def list_all(self) -> List[Plan]:
        """Every plan, active first, then by fee.

        Returns:
            List[Plan]: The plans.
        """
        async with self._sessionmaker() as session:
            rows = await session.execute(
                select(PlanModel).order_by(PlanModel.active.desc(), PlanModel.monthly_fee_micros, PlanModel.name)
            )
            return [_to_plan(row) for row in rows.scalars()]

    async def get(self, plan_id: UUID) -> Optional[Plan]:
        """Fetch a plan.

        Args:
            plan_id (UUID): Plan id.

        Returns:
            Optional[Plan]: The plan, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(PlanModel, plan_id)
            return _to_plan(model) if model else None

    async def create(self, plan: Plan) -> Plan:
        """Store a new plan.

        Args:
            plan (Plan): The plan.

        Returns:
            Plan: The stored plan.

        Raises:
            AlreadyExistsError: If its code is taken.
        """
        async with self._sessionmaker() as session:
            model = PlanModel(**plan.model_dump(exclude={"created_at", "updated_at"}))
            session.add(model)
            with duplicate_as_already_exists():
                await session.commit()
            await session.refresh(model)
            return _to_plan(model)

    async def update(self, plan_id: UUID, **fields: object) -> Optional[Plan]:
        """Change some fields of a plan.

        Args:
            plan_id (UUID): Plan id.
            **fields (object): Fields to set.

        Returns:
            Optional[Plan]: The updated plan, or None.

        Raises:
            AlreadyExistsError: If the new code is taken.
        """
        async with self._sessionmaker() as session:
            model = await session.get(PlanModel, plan_id)
            if model is None:
                return None
            for key, value in fields.items():
                setattr(model, key, value)
            with duplicate_as_already_exists():
                await session.commit()
            await session.refresh(model)
            return _to_plan(model)

    async def delete(self, plan_id: UUID) -> bool:
        """Delete a plan no subscription uses.

        Args:
            plan_id (UUID): Plan id.

        Returns:
            bool: True if it existed.

        Raises:
            PlanInUseError: If a subscription references it.
        """
        async with self._sessionmaker() as session:
            in_use = await session.scalar(
                select(func.count()).select_from(TenantSubscriptionModel).where(TenantSubscriptionModel.plan_id == plan_id)
            )
            if in_use:
                raise PlanInUseError(f"plan {plan_id} has {in_use} subscription(s)")
            model = await session.get(PlanModel, plan_id)
            if model is None:
                return False
            await session.delete(model)
            await session.commit()
            return True


class SqlAlchemySubscriptionRepository(SubscriptionRepositoryPort):
    """Postgres-backed tenant subscriptions."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def get(self, tenant_id: UUID) -> Optional[TenantSubscription]:
        """A tenant's subscription.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            Optional[TenantSubscription]: It, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(TenantSubscriptionModel, tenant_id)
            return _to_subscription(model) if model else None

    async def list_all(self) -> List[TenantSubscription]:
        """Every subscription.

        Returns:
            List[TenantSubscription]: The subscriptions.
        """
        async with self._sessionmaker() as session:
            rows = await session.execute(select(TenantSubscriptionModel))
            return [_to_subscription(row) for row in rows.scalars()]

    async def upsert(self, subscription: TenantSubscription) -> TenantSubscription:
        """Create or replace a tenant's subscription.

        Args:
            subscription (TenantSubscription): The subscription.

        Returns:
            TenantSubscription: The stored subscription.
        """
        values = subscription.model_dump(exclude={"updated_at"})
        statement = (
            insert(TenantSubscriptionModel)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["tenant_id"],
                set_={**{k: v for k, v in values.items() if k != "tenant_id"}, "updated_at": func.now()},
            )
            .returning(TenantSubscriptionModel)
        )
        async with self._sessionmaker() as session:
            model = (await session.execute(statement)).scalar_one()
            await session.commit()
            return _to_subscription(model)

    async def delete(self, tenant_id: UUID) -> bool:
        """Remove a tenant's subscription.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            bool: True if it existed.
        """
        async with self._sessionmaker() as session:
            model = await session.get(TenantSubscriptionModel, tenant_id)
            if model is None:
                return False
            await session.delete(model)
            await session.commit()
            return True


class SqlAlchemyStatementRepository(StatementRepositoryPort):
    """Postgres-backed closed statements."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def get(self, tenant_id: UUID, period: str) -> Optional[BillingStatement]:
        """A tenant's closed statement for a period.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".

        Returns:
            Optional[BillingStatement]: It, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.scalar(
                select(UsageStatementModel).where(
                    UsageStatementModel.tenant_id == tenant_id, UsageStatementModel.period == period
                )
            )
            return BillingStatement.model_validate(model.data) if model else None

    async def list_by_tenant(self, tenant_id: UUID) -> List[BillingStatement]:
        """A tenant's closed statements, newest first.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            List[BillingStatement]: The statements.
        """
        async with self._sessionmaker() as session:
            rows = await session.execute(
                select(UsageStatementModel)
                .where(UsageStatementModel.tenant_id == tenant_id)
                .order_by(UsageStatementModel.period.desc())
            )
            return [BillingStatement.model_validate(row.data) for row in rows.scalars()]

    async def save_closed(self, statement: BillingStatement) -> bool:
        """Store a closed statement unless the period is already closed.

        Args:
            statement (BillingStatement): The statement.

        Returns:
            bool: True if stored.
        """
        values = dict(
            tenant_id=statement.tenant_id,
            period=statement.period,
            status="closed",
            revenue_micros=statement.revenue_micros,
            cost_micros=statement.cost_micros,
            data=statement.model_dump(mode="json"),
        )
        statement_sql = (
            insert(UsageStatementModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["tenant_id", "period"])
            .returning(UsageStatementModel.id)
        )
        async with self._sessionmaker() as session:
            inserted = (await session.execute(statement_sql)).scalar_one_or_none()
            await session.commit()
            return inserted is not None
