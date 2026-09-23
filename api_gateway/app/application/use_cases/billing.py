"""Use cases for statements, period closing, pricing insight and the
cost catalog's coverage."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from app.domain.models.billing import (
    BillingStatement,
    ChannelPricingInsight,
    build_statement,
    month_bounds,
    pricing_insight,
)
from app.domain.models.usage import SKU_AI_MESSAGE, CostCatalog, RatedUsage
from app.domain.ports.outbound import (
    CostRateRepositoryPort,
    PlanRepositoryPort,
    StatementRepositoryPort,
    SubscriptionRepositoryPort,
    UsageStorePort,
)

logger = logging.getLogger("usecase.billing")


class PlanNotFoundError(Exception):
    """The requested plan does not exist."""


async def _rated(
    usage: UsageStorePort,
    rates: CostRateRepositoryPort,
    *,
    start: datetime,
    end: datetime,
    tenant_id: Optional[UUID] = None,
) -> List[RatedUsage]:
    """Daily usage in [start, end) rated with the current catalog.

    Args:
        usage (UsageStorePort): Usage archive.
        rates (CostRateRepositoryPort): Cost catalog.
        start (datetime): Inclusive start.
        end (datetime): Exclusive end.
        tenant_id (Optional[UUID]): One tenant, or all.

    Returns:
        List[RatedUsage]: The rated aggregates.
    """
    catalog = CostCatalog(await rates.list_all())
    return [catalog.rate(row) for row in await usage.aggregate_daily(start=start, end=end, tenant_id=tenant_id)]


class ComputeStatementUseCase:
    """A tenant's statement for a month: the frozen one if the period is
    closed, otherwise a live preview computed from current usage, plan
    and cost catalog."""

    def __init__(
        self,
        *,
        usage_store: UsageStorePort,
        cost_rates: CostRateRepositoryPort,
        plans: PlanRepositoryPort,
        subscriptions: SubscriptionRepositoryPort,
        statements: StatementRepositoryPort,
    ) -> None:
        """Build the use case.

        Args:
            usage_store (UsageStorePort): Usage archive.
            cost_rates (CostRateRepositoryPort): Cost catalog.
            plans (PlanRepositoryPort): Plans.
            subscriptions (SubscriptionRepositoryPort): Subscriptions.
            statements (StatementRepositoryPort): Closed statements.
        """
        self._usage = usage_store
        self._rates = cost_rates
        self._plans = plans
        self._subscriptions = subscriptions
        self._statements = statements

    async def execute(self, *, tenant_id: UUID, period: str, now: datetime) -> BillingStatement:
        """Get or compute the statement.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            now (datetime): Current time.

        Returns:
            BillingStatement: Closed or preview statement.

        Raises:
            ValueError: If `period` is malformed.
        """
        closed = await self._statements.get(tenant_id, period)
        if closed is not None:
            return closed
        return await self.preview(tenant_id=tenant_id, period=period, now=now)

    async def preview(self, *, tenant_id: UUID, period: str, now: datetime) -> BillingStatement:
        """Compute the live statement, ignoring any closed one.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            now (datetime): Current time.

        Returns:
            BillingStatement: A "preview" statement.
        """
        start, end = month_bounds(period)
        subscription = await self._subscriptions.get(tenant_id)
        plan = await self._plans.get(subscription.plan_id) if subscription else None
        rated = await _rated(self._usage, self._rates, start=start, end=min(end, now), tenant_id=tenant_id)
        return build_statement(
            tenant_id=tenant_id, period=period, rated=rated, plan=plan, subscription=subscription, now=now
        )


class CloseBillingPeriodUseCase:
    """Freezes every subscribed tenant's statement for a finished month.

    Idempotent: a period already closed for a tenant is skipped, so the
    worker can run it every day.
    """

    def __init__(
        self,
        *,
        compute: ComputeStatementUseCase,
        subscriptions: SubscriptionRepositoryPort,
        statements: StatementRepositoryPort,
        grace: timedelta = timedelta(hours=6),
    ) -> None:
        """Build the use case.

        Args:
            compute (ComputeStatementUseCase): Computes the statements.
            subscriptions (SubscriptionRepositoryPort): Who to close for.
            statements (StatementRepositoryPort): Where they are frozen.
            grace (timedelta): Wait after the month ends before closing, so
                usage still in transit (event stream, LLM usage sync lag)
                lands in the right month first.
        """
        self._compute = compute
        self._subscriptions = subscriptions
        self._statements = statements
        self._grace = grace

    def closable_at(self, period: str) -> datetime:
        """When a period may be closed.

        Args:
            period (str): "YYYY-MM".

        Returns:
            datetime: End of the month plus the grace period.
        """
        return month_bounds(period)[1] + self._grace

    async def execute(self, *, period: str, now: datetime) -> int:
        """Close the period for every subscribed tenant.

        Args:
            period (str): "YYYY-MM" - must already be over.
            now (datetime): Current time.

        Returns:
            int: Statements closed in this run.

        Raises:
            ValueError: If the period is not closable yet (see closable_at).
        """
        if now < self.closable_at(period):
            raise ValueError(f"period {period} cannot be closed before {self.closable_at(period).isoformat()}")
        closed = 0
        for subscription in await self._subscriptions.list_all():
            if await self._statements.get(subscription.tenant_id, period) is not None:
                continue
            statement = await self._compute.preview(tenant_id=subscription.tenant_id, period=period, now=now)
            if await self._statements.save_closed(statement.model_copy(update={"status": "closed"})):
                closed += 1
        if closed:
            logger.info("billing.period.closed", extra={"period": period, "statements": closed})
        return closed


class PlanPricingInsightUseCase:
    """Average cost per AI-handled message per channel and the overage
    price the plan's margin suggests.

    Uses the usage of the tenants subscribed to the plan; if none has
    usage yet, the whole platform's (a new plan still gets a suggestion).
    """

    def __init__(
        self,
        *,
        usage_store: UsageStorePort,
        cost_rates: CostRateRepositoryPort,
        plans: PlanRepositoryPort,
        subscriptions: SubscriptionRepositoryPort,
    ) -> None:
        """Build the use case.

        Args:
            usage_store (UsageStorePort): Usage archive.
            cost_rates (CostRateRepositoryPort): Cost catalog.
            plans (PlanRepositoryPort): Plans.
            subscriptions (SubscriptionRepositoryPort): Who is on each plan.
        """
        self._usage = usage_store
        self._rates = cost_rates
        self._plans = plans
        self._subscriptions = subscriptions

    async def execute(self, *, plan_id: UUID, now: datetime, days: int = 30) -> "PricingInsightResult":
        """Compute the insight.

        Args:
            plan_id (UUID): Plan id.
            now (datetime): Current time.
            days (int): Sample length.

        Returns:
            PricingInsightResult: Per-channel figures and the sample used.

        Raises:
            PlanNotFoundError: If the plan does not exist.
        """
        plan = await self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFoundError(str(plan_id))
        tenants = {s.tenant_id for s in await self._subscriptions.list_all() if s.plan_id == plan_id}
        rated = await _rated(self._usage, self._rates, start=now - timedelta(days=days), end=now)
        own = [r for r in rated if r.usage.tenant_id in tenants]
        sample = "plan" if any(r.usage.sku == SKU_AI_MESSAGE for r in own) else "platform"
        return PricingInsightResult(
            plan_id=plan_id,
            margin_pct=Decimal(plan.margin_pct),
            days=days,
            sample=sample,
            channels=pricing_insight(plan, own if sample == "plan" else rated),
        )


@dataclass(frozen=True)
class PricingInsightResult:
    """Output of PlanPricingInsightUseCase.

    Attributes:
        plan_id (UUID): Plan id.
        margin_pct (Decimal): The plan's target margin.
        days (int): Sample length in days.
        sample (str): "plan" (its tenants' usage) or "platform" (everyone's).
        channels (List[ChannelPricingInsight]): Per-channel figures.
    """

    plan_id: UUID
    margin_pct: Decimal
    days: int
    sample: str
    channels: List[ChannelPricingInsight]


@dataclass(frozen=True)
class UnratedMeter:
    """A meter with recent usage but no applicable cost rate.

    Attributes:
        kind (str): Kind of usage.
        provider (str): Provider.
        sku (str): SKU.
        unit (str): Unit.
        quantity (Decimal): Unrated quantity in the window.
    """

    kind: str
    provider: str
    sku: str
    unit: str
    quantity: Decimal


class ListUnratedMetersUseCase:
    """Meters used recently that no cost rate covers - their cost counts
    as 0 until the admin adds a rate (which then applies retroactively,
    except to closed statements)."""

    def __init__(self, *, usage_store: UsageStorePort, cost_rates: CostRateRepositoryPort) -> None:
        """Build the use case.

        Args:
            usage_store (UsageStorePort): Usage archive.
            cost_rates (CostRateRepositoryPort): Cost catalog.
        """
        self._usage = usage_store
        self._rates = cost_rates

    async def execute(self, *, now: datetime, days: int = 30) -> List[UnratedMeter]:
        """List unrated meters.

        Args:
            now (datetime): Current time.
            days (int): Window length.

        Returns:
            List[UnratedMeter]: One per meter, largest quantity first.
        """
        totals: dict = {}
        for item in await _rated(self._usage, self._rates, start=now - timedelta(days=days), end=now):
            if not item.missing_rate:
                continue
            u = item.usage
            key = (u.kind, u.provider, u.sku, u.unit)
            totals[key] = totals.get(key, Decimal(0)) + u.quantity
        return [
            UnratedMeter(kind=k[0], provider=k[1], sku=k[2], unit=k[3], quantity=q)
            for k, q in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        ]
