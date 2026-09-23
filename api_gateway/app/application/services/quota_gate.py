"""QuotaGate: decides, per inbound message, whether the tenant's plan
admits handing it to an app, and keeps the live counters and alerts.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, Tuple
from uuid import UUID

from app.domain.models.billing import (
    Plan,
    QuotaDecision,
    TenantSubscription,
    evaluate_quota,
    month_bounds,
    period_of,
)
from app.domain.models.usage import SKU_AI_MESSAGE
from app.domain.ports.outbound import (
    PlanRepositoryPort,
    QuotaCounterPort,
    SubscriptionRepositoryPort,
    UsageStorePort,
)

logger = logging.getLogger("billing.quota_gate")


class QuotaAlertNotifier(Protocol):
    """Receives quota alerts (implemented by QuotaAlertMailer)."""

    async def notify(self, *, tenant_id: UUID, period: str, decision: QuotaDecision, event: str) -> None:
        """Deliver one alert.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            decision (QuotaDecision): The decision that triggered it.
            event (str): "80", "100" (% of the included messages) or
                "blocked" (first message refused this month).
        """
        ...


class QuotaGate:
    """Admits or refuses AI-handled messages according to each tenant's
    plan, and counts the admitted ones.

    Tenants without a subscription are always admitted (and not counted).
    Subscriptions and plans are cached for `cache_ttl_seconds` so the hot
    path does not hit Postgres on every message; admin changes made in
    this process call `invalidate()`, other processes pick them up when
    the cache expires. Counters that are missing (first message of the
    month, or Redis lost them) are rebuilt from the usage archive.
    """

    def __init__(
        self,
        *,
        subscriptions: SubscriptionRepositoryPort,
        plans: PlanRepositoryPort,
        counters: QuotaCounterPort,
        usage_store: Optional[UsageStorePort] = None,
        notifier: Optional[QuotaAlertNotifier] = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        """Build the gate.

        Args:
            subscriptions (SubscriptionRepositoryPort): Tenant subscriptions.
            plans (PlanRepositoryPort): Plans.
            counters (QuotaCounterPort): Live monthly counters.
            usage_store (Optional[UsageStorePort]): Used to rebuild missing
                counters; without it they restart at 0.
            notifier (Optional[QuotaAlertNotifier]): Receives alerts.
            cache_ttl_seconds (float): Subscription/plan cache lifetime.
        """
        self._subscriptions = subscriptions
        self._plans = plans
        self._counters = counters
        self._usage = usage_store
        self._notifier = notifier
        self._ttl = cache_ttl_seconds
        self._cache: Dict[Any, Tuple[float, Any]] = {}

    def invalidate(self, tenant_id: Optional[UUID] = None) -> None:
        """Drop cached subscriptions/plans (all, or one tenant's subscription).

        Args:
            tenant_id (Optional[UUID]): Tenant to drop; None = everything.
        """
        if tenant_id is None:
            self._cache.clear()
        else:
            self._cache.pop(("subscription", tenant_id), None)

    async def admit(self, *, tenant_id: UUID, channel_type: str, now: datetime) -> QuotaDecision:
        """Decide on one inbound message and count it if admitted.

        Args:
            tenant_id (UUID): Tenant the message is for.
            channel_type (str): Channel it came through.
            now (datetime): Current time (timezone-aware).

        Returns:
            QuotaDecision: The decision.
        """
        subscription: Optional[TenantSubscription] = await self._cached(
            ("subscription", tenant_id), lambda: self._subscriptions.get(tenant_id)
        )
        if subscription is None:
            return QuotaDecision(allowed=True, reason="no_subscription", channel_type=channel_type)
        plan: Optional[Plan] = await self._cached(("plan", subscription.plan_id), lambda: self._plans.get(subscription.plan_id))
        if plan is None:
            return QuotaDecision(allowed=True, reason="no_subscription", channel_type=channel_type)

        period = period_of(now)
        counts = await self._counts(tenant_id, period, now)
        decision = evaluate_quota(plan, subscription, channel_type, counts)

        if decision.allowed:
            await self._counters.increment(tenant_id, period, channel_type)
            for threshold in decision.thresholds_crossed:
                await self._alert(tenant_id, period, decision, str(threshold))
        else:
            logger.warning(
                "billing.quota.refused",
                extra={"tenant_id": str(tenant_id), "channel_type": channel_type, "reason": decision.reason},
            )
            await self._alert(tenant_id, period, decision, "blocked")
        return decision

    async def _counts(self, tenant_id: UUID, period: str, now: datetime) -> Dict[str, int]:
        """This month's counters, rebuilt from the usage archive if missing.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            now (datetime): Current time.

        Returns:
            Dict[str, int]: Channel -> messages used.
        """
        counts = await self._counters.get_all(tenant_id, period)
        if counts is not None:
            return counts
        seeded: Dict[str, int] = {}
        if self._usage is not None:
            start, _ = month_bounds(period)
            for row in await self._usage.aggregate_daily(start=start, end=now, tenant_id=tenant_id):
                if row.kind == "platform" and row.sku == SKU_AI_MESSAGE:
                    seeded[row.channel_type] = seeded.get(row.channel_type, 0) + int(row.quantity)
        await self._counters.seed(tenant_id, period, seeded)
        return await self._counters.get_all(tenant_id, period) or seeded

    async def _alert(self, tenant_id: UUID, period: str, decision: QuotaDecision, event: str) -> None:
        """Send an alert once per tenant, period, channel and event. Never raises.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            decision (QuotaDecision): The triggering decision.
            event (str): "80", "100" or "blocked".
        """
        if self._notifier is None:
            return
        try:
            if await self._counters.first_time(f"{tenant_id}:{period}:{decision.channel_type}:{event}"):
                await self._notifier.notify(tenant_id=tenant_id, period=period, decision=decision, event=event)
        except Exception:
            logger.error("billing.quota.alert_failed", extra={"tenant_id": str(tenant_id)}, exc_info=True)

    async def _cached(self, key: Any, load) -> Any:
        """Memoize a lookup for the cache lifetime.

        Args:
            key (Any): Cache key.
            load: Zero-argument async loader.

        Returns:
            Any: The cached or freshly loaded value (None is cached too).
        """
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        value = await load()
        self._cache[key] = (time.monotonic() + self._ttl, value)
        return value
