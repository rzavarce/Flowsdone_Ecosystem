"""Use case for Flowsdone's commercial catalog: plans, tenant subscriptions,
the cost catalog and closed statements.

The admin HTTP endpoints only validate input, check access and shape the
response; the rules live here:

- a tenant can only subscribe to an existing, active plan;
- changing a tenant's plan keeps the date its subscription started;
- any change to plans or subscriptions invalidates the quota gate's cache,
  so the next message is judged by the new terms;
- a plan with subscribers can't be deleted (deactivate it instead).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.models.billing import BillingStatement, Plan, TenantSubscription
from app.domain.models.usage import CostRate
from app.domain.ports.outbound import (
    CostRateRepositoryPort,
    PlanRepositoryPort,
    StatementRepositoryPort,
    SubscriptionRepositoryPort,
    TenantRepositoryPort,
)


class InactivePlanError(ValueError):
    """The plan doesn't exist or can't be assigned (maps to 400)."""


@dataclass(frozen=True)
class PlanWithSubscribers:
    """A plan and how many tenants are subscribed to it.

    Attributes:
        plan (Plan): The plan.
        subscribers (int): Tenants subscribed to it.
    """

    plan: Plan
    subscribers: int


class ManageBillingCatalogUseCase:
    """Plans, subscriptions, cost rates and statements for the admin API."""

    def __init__(
        self,
        *,
        plans: PlanRepositoryPort,
        subscriptions: SubscriptionRepositoryPort,
        cost_rates: CostRateRepositoryPort,
        statements: StatementRepositoryPort,
        tenants: TenantRepositoryPort,
        quota_gate: Optional[Any] = None,
    ) -> None:
        """Build the use case.

        Args:
            plans (PlanRepositoryPort): Plans.
            subscriptions (SubscriptionRepositoryPort): Tenant subscriptions.
            cost_rates (CostRateRepositoryPort): Cost catalog.
            statements (StatementRepositoryPort): Closed statements.
            tenants (TenantRepositoryPort): To check a tenant exists.
            quota_gate (Optional[Any]): The QuotaGate whose cache must be
                dropped when plans or subscriptions change (optional).
        """
        self._plans = plans
        self._subscriptions = subscriptions
        self._cost_rates = cost_rates
        self._statements = statements
        self._tenants = tenants
        self._quota_gate = quota_gate

    def _invalidate(self, tenant_id: Optional[UUID] = None) -> None:
        """Make the quota gate re-read plans/subscriptions.

        Args:
            tenant_id (Optional[UUID]): Tenant changed; None = everything.
        """
        if self._quota_gate is not None:
            self._quota_gate.invalidate(tenant_id)

    async def _subscriber_counts(self) -> Dict[UUID, int]:
        """Subscribers per plan.

        Returns:
            Dict[UUID, int]: Plan id -> number of subscribed tenants.
        """
        counts: Dict[UUID, int] = {}
        for subscription in await self._subscriptions.list_all():
            counts[subscription.plan_id] = counts.get(subscription.plan_id, 0) + 1
        return counts

    # ------------------------------------------------------------- plans

    async def list_plans(self) -> List[PlanWithSubscribers]:
        """Every plan with its subscriber count.

        Returns:
            List[PlanWithSubscribers]: The plans.
        """
        counts = await self._subscriber_counts()
        return [PlanWithSubscribers(p, counts.get(p.id, 0)) for p in await self._plans.list_all()]

    async def create_plan(self, fields: Dict[str, Any]) -> PlanWithSubscribers:
        """Create a plan.

        Args:
            fields (Dict[str, Any]): The plan's fields (without id).

        Returns:
            PlanWithSubscribers: The plan (no subscribers yet).

        Raises:
            AlreadyExistsError: If the code is taken.
        """
        plan = await self._plans.create(Plan(id=uuid4(), **fields))
        return PlanWithSubscribers(plan, 0)

    async def update_plan(self, plan_id: UUID, fields: Dict[str, Any]) -> Optional[PlanWithSubscribers]:
        """Edit a plan; its subscribers are judged by it from the next message.

        Args:
            plan_id (UUID): Plan id.
            fields (Dict[str, Any]): Fields to change.

        Returns:
            Optional[PlanWithSubscribers]: The plan, or None if it doesn't exist.
        """
        plan = await self._plans.update(plan_id, **fields)
        if plan is None:
            return None
        self._invalidate()
        return PlanWithSubscribers(plan, (await self._subscriber_counts()).get(plan.id, 0))

    async def delete_plan(self, plan_id: UUID) -> bool:
        """Delete a plan nobody is subscribed to.

        Args:
            plan_id (UUID): Plan id.

        Returns:
            bool: False if it doesn't exist.

        Raises:
            PlanInUseError: If tenants are subscribed to it.
        """
        return await self._plans.delete(plan_id)

    # ------------------------------------------------------ subscriptions

    async def tenant_exists(self, tenant_id: UUID) -> bool:
        """Whether a tenant exists.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            bool: True if it exists.
        """
        return await self._tenants.get_by_id(tenant_id) is not None

    async def get_subscription(self, tenant_id: UUID) -> Optional[Tuple[TenantSubscription, Plan]]:
        """A tenant's subscription and its plan.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            Optional[Tuple[TenantSubscription, Plan]]: None if it has none.
        """
        subscription = await self._subscriptions.get(tenant_id)
        if subscription is None:
            return None
        plan = await self._plans.get(subscription.plan_id)
        return (subscription, plan) if plan is not None else None

    async def subscribe(
        self,
        tenant_id: UUID,
        *,
        plan_id: UUID,
        overage_mode: Optional[str],
        spending_cap_micros: Optional[int],
        now: datetime,
    ) -> Tuple[TenantSubscription, Plan]:
        """Subscribe a tenant to a plan, or change its plan/overrides.

        The month's usage so far counts against the new plan; the date the
        subscription started is kept when only the plan changes.

        Args:
            tenant_id (UUID): Tenant id.
            plan_id (UUID): Plan to subscribe to.
            overage_mode (Optional[str]): Override of the plan's mode.
            spending_cap_micros (Optional[int]): Overage spending cap.
            now (datetime): Current time (start date of a new subscription).

        Returns:
            Tuple[TenantSubscription, Plan]: The subscription and its plan.

        Raises:
            InactivePlanError: If the plan doesn't exist or is inactive.
        """
        plan = await self._plans.get(plan_id)
        if plan is None or not plan.active:
            raise InactivePlanError("plan not found or inactive")
        current = await self._subscriptions.get(tenant_id)
        subscription = await self._subscriptions.upsert(
            TenantSubscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                overage_mode=overage_mode,
                spending_cap_micros=spending_cap_micros,
                started_at=current.started_at if current else now,
            )
        )
        self._invalidate(tenant_id)
        return subscription, plan

    async def unsubscribe(self, tenant_id: UUID) -> bool:
        """Remove a tenant's subscription: no limits and no charges from now on.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            bool: False if it had none.
        """
        removed = await self._subscriptions.delete(tenant_id)
        if removed:
            self._invalidate(tenant_id)
        return removed

    # ------------------------------------------------- cost catalog / statements

    async def list_cost_rates(self) -> List[CostRate]:
        """The cost catalog.

        Returns:
            List[CostRate]: Every rate.
        """
        return await self._cost_rates.list_all()

    async def create_cost_rate(self, rate: CostRate) -> CostRate:
        """Add a rate (a price change is a new rate with its start date).

        Args:
            rate (CostRate): The rate.

        Returns:
            CostRate: The rate as stored.
        """
        return await self._cost_rates.create(rate)

    async def delete_cost_rate(self, rate_id: UUID) -> bool:
        """Delete a rate loaded by mistake.

        Args:
            rate_id (UUID): Rate id.

        Returns:
            bool: False if it doesn't exist.
        """
        return await self._cost_rates.delete(rate_id)

    async def closed_statements(self, tenant_id: UUID) -> List[BillingStatement]:
        """A tenant's closed monthly statements.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            List[BillingStatement]: The statements.
        """
        return await self._statements.list_by_tenant(tenant_id)
