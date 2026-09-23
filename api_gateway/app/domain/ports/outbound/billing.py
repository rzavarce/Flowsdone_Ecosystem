"""Ports for plans, subscriptions, statements and live quota counters."""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol
from uuid import UUID

from app.domain.models.billing import BillingStatement, Plan, TenantSubscription


class PlanInUseError(Exception):
    """A plan cannot be deleted while a subscription references it."""


class PlanRepositoryPort(Protocol):
    """Commercial plans."""

    async def list_all(self) -> List[Plan]:
        """Every plan, active first.

        Returns:
            List[Plan]: The plans.
        """
        ...

    async def get(self, plan_id: UUID) -> Optional[Plan]:
        """Fetch a plan.

        Args:
            plan_id (UUID): Plan id.

        Returns:
            Optional[Plan]: The plan, or None.
        """
        ...

    async def create(self, plan: Plan) -> Plan:
        """Store a new plan.

        Args:
            plan (Plan): The plan.

        Returns:
            Plan: The stored plan.

        Raises:
            AlreadyExistsError: If its code is taken.
        """
        ...

    async def update(self, plan_id: UUID, **fields: object) -> Optional[Plan]:
        """Change some fields of a plan.

        Args:
            plan_id (UUID): Plan id.
            **fields (object): Fields to set.

        Returns:
            Optional[Plan]: The updated plan, or None if it doesn't exist.

        Raises:
            AlreadyExistsError: If the new code is taken.
        """
        ...

    async def delete(self, plan_id: UUID) -> bool:
        """Delete a plan no subscription uses.

        Args:
            plan_id (UUID): Plan id.

        Returns:
            bool: True if it existed.

        Raises:
            PlanInUseError: If a subscription still references it.
        """
        ...


class SubscriptionRepositoryPort(Protocol):
    """Which plan each tenant is on (at most one subscription per tenant)."""

    async def get(self, tenant_id: UUID) -> Optional[TenantSubscription]:
        """A tenant's subscription.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            Optional[TenantSubscription]: It, or None if not subscribed.
        """
        ...

    async def list_all(self) -> List[TenantSubscription]:
        """Every subscription.

        Returns:
            List[TenantSubscription]: The subscriptions.
        """
        ...

    async def upsert(self, subscription: TenantSubscription) -> TenantSubscription:
        """Create or replace a tenant's subscription.

        Args:
            subscription (TenantSubscription): The subscription.

        Returns:
            TenantSubscription: The stored subscription.
        """
        ...

    async def delete(self, tenant_id: UUID) -> bool:
        """Remove a tenant's subscription.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            bool: True if it existed.
        """
        ...


class StatementRepositoryPort(Protocol):
    """Closed (frozen) monthly statements."""

    async def get(self, tenant_id: UUID, period: str) -> Optional[BillingStatement]:
        """A tenant's closed statement for a period.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".

        Returns:
            Optional[BillingStatement]: It, or None if not closed yet.
        """
        ...

    async def list_by_tenant(self, tenant_id: UUID) -> List[BillingStatement]:
        """A tenant's closed statements, newest first.

        Args:
            tenant_id (UUID): Tenant id.

        Returns:
            List[BillingStatement]: The statements.
        """
        ...

    async def save_closed(self, statement: BillingStatement) -> bool:
        """Store a closed statement unless one exists for that tenant and
        period (a closed period is never overwritten).

        Args:
            statement (BillingStatement): The statement (status "closed").

        Returns:
            bool: True if stored, False if it already existed.
        """
        ...


class QuotaCounterPort(Protocol):
    """Live per-month counters of AI-handled messages, per tenant and
    channel (Redis) - what quota decisions read on every message. The
    usage archive stays the source of truth for statements.
    """

    async def get_all(self, tenant_id: UUID, period: str) -> Optional[Dict[str, int]]:
        """This period's counters of a tenant.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".

        Returns:
            Optional[Dict[str, int]]: Channel -> messages, or None if the
            counters were never initialized (e.g. after a Redis restart).
        """
        ...

    async def seed(self, tenant_id: UUID, period: str, counts: Dict[str, int]) -> None:
        """Initialize the counters (keeping any value already there).

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            counts (Dict[str, int]): Channel -> messages already used.
        """
        ...

    async def increment(self, tenant_id: UUID, period: str, channel_type: str, by: int = 1) -> int:
        """Add to a channel's counter.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            channel_type (str): Channel.
            by (int): Amount (negative to undo).

        Returns:
            int: The new value.
        """
        ...

    async def first_time(self, key: str) -> bool:
        """Atomically mark a one-off event (e.g. an alert) as done.

        Args:
            key (str): Event key (tenant/period/channel/threshold).

        Returns:
            bool: True the first time for this key, False afterwards.
        """
        ...
