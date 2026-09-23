"""Admin endpoints for plans, the cost catalog, tenant subscriptions,
statements and period closing.

Plans and the cost catalog are Flowsdone's own pricing and costs (admin
only). Subscriptions and statements are readable by managers of the
tenant, but costs and margins are stripped for anyone but admin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.billing_schemas import (
    ChannelPricingOut,
    ClosePeriodOut,
    CostRateCreate,
    CostRateOut,
    PlanCreate,
    PlanFields,
    PlanOut,
    PricingInsightOut,
    StatementChannelOut,
    StatementOut,
    SubscriptionOut,
    SubscriptionUpdate,
    UnratedMeterOut,
    UsageLineOut,
)
from app.application.use_cases.billing import PlanNotFoundError
from app.domain.models.billing import BillingStatement, Plan, TenantSubscription, month_bounds, period_of
from app.domain.models.usage import CostRate
from app.domain.ports.outbound import PlanInUseError

router = APIRouter(tags=["admin:billing"])

_PERIOD = r"^\d{4}-(0[1-9]|1[0-2])$"


def _now() -> datetime:
    """Current UTC time (patched in tests).

    Returns:
        datetime: Now.
    """
    return datetime.now(timezone.utc)


async def _plan_out(request: Request, plan: Plan) -> PlanOut:
    """Build a PlanOut with its subscription count.

    Args:
        request (Request): Used to reach the subscription repository.
        plan (Plan): The plan.

    Returns:
        PlanOut: The response.
    """
    subscriptions = await request.app.state.subscription_repo.list_all()
    return PlanOut(**plan.model_dump(), subscriptions=sum(1 for s in subscriptions if s.plan_id == plan.id))


def _invalidate_quota_cache(request: Request, tenant_id: Optional[UUID] = None) -> None:
    """Make the quota gate re-read subscriptions/plans in this process.

    Args:
        request (Request): Used to reach `request.app.state.quota_gate`.
        tenant_id (Optional[UUID]): Tenant changed; None = everything.
    """
    gate = getattr(request.app.state, "quota_gate", None)
    if gate is not None:
        gate.invalidate(tenant_id)


def statement_out(statement: BillingStatement, *, with_costs: bool) -> StatementOut:
    """Convert a statement to its response, stripping costs if needed.

    Args:
        statement (BillingStatement): The statement.
        with_costs (bool): Keep costs and margins (admin) or null them.

    Returns:
        StatementOut: The response.
    """
    data = statement.model_dump(exclude={"channels", "costs"})
    out = StatementOut(
        **data,
        channels=[
            StatementChannelOut(**{**line.model_dump(), "cost_micros": line.cost_micros if with_costs else None})
            for line in statement.channels
        ],
        costs=[UsageLineOut(**c.model_dump()) for c in statement.costs] if with_costs else None,
    )
    if not with_costs:
        out.cost_micros = out.margin_micros = out.margin_pct = out.unrated_meters = None
    return out


async def _existing_tenant(request: Request, access: AdminAccess, tenant_id: UUID) -> None:
    """Require a tenant that exists and is in scope (404 otherwise).

    Args:
        request (Request): Used to reach the tenant repository.
        access (AdminAccess): The caller.
        tenant_id (UUID): Tenant id.

    Raises:
        HTTPException: 404.
    """
    access.tenant(tenant_id)
    if not await request.app.state.tenant_repo.get_by_id(tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")


# --------------------------------------------------------------------- plans


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(request: Request, _: AdminAccess = Depends(admin_access("plans", "read"))) -> list[PlanOut]:
    """Every plan (admin only).

    Args:
        request (Request): Used to reach the plan repository.
        _ (AdminAccess): The caller.

    Returns:
        list[PlanOut]: The plans, with how many tenants use each.
    """
    subscriptions = await request.app.state.subscription_repo.list_all()
    return [
        PlanOut(**plan.model_dump(), subscriptions=sum(1 for s in subscriptions if s.plan_id == plan.id))
        for plan in await request.app.state.plan_repo.list_all()
    ]


@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(
    body: PlanCreate, request: Request, _: AdminAccess = Depends(admin_access("plans", "write"))
) -> PlanOut:
    """Create a plan (admin only).

    Args:
        body (PlanCreate): The plan.
        request (Request): Used to reach the plan repository.
        _ (AdminAccess): The caller.

    Returns:
        PlanOut: The created plan.

    Raises:
        AlreadyExistsError: If the code is taken (409).
    """
    fields = body.model_dump(exclude_none=True)
    plan = await request.app.state.plan_repo.create(Plan(id=uuid4(), **fields))
    return await _plan_out(request, plan)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: UUID, body: PlanFields, request: Request, _: AdminAccess = Depends(admin_access("plans", "write"))
) -> PlanOut:
    """Edit a plan (admin only). Applies to its subscribers right away;
    statements already closed keep the figures they were closed with.

    Args:
        plan_id (UUID): Plan id.
        body (PlanFields): Fields to change (unset = unchanged).
        request (Request): Used to reach the plan repository.
        _ (AdminAccess): The caller.

    Returns:
        PlanOut: The updated plan.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    plan = await request.app.state.plan_repo.update(plan_id, **body.model_dump(exclude_unset=True))
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    _invalidate_quota_cache(request)
    return await _plan_out(request, plan)


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: UUID, request: Request, _: AdminAccess = Depends(admin_access("plans", "write"))) -> Response:
    """Delete a plan nobody is subscribed to (admin only).

    Args:
        plan_id (UUID): Plan id.
        request (Request): Used to reach the plan repository.
        _ (AdminAccess): The caller.

    Returns:
        Response: 204.

    Raises:
        HTTPException: 404 if it does not exist, 409 if in use (deactivate it instead).
    """
    try:
        deleted = await request.app.state.plan_repo.delete(plan_id)
    except PlanInUseError as exc:
        raise HTTPException(status_code=409, detail="plan in use") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="plan not found")
    return Response(status_code=204)


@router.get("/plans/{plan_id}/pricing-insight", response_model=PricingInsightOut)
async def plan_pricing_insight(
    plan_id: UUID,
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    _: AdminAccess = Depends(admin_access("plans", "read")),
) -> PricingInsightOut:
    """Average cost per message per channel and the suggested overage
    price for the plan's margin (admin only).

    Args:
        plan_id (UUID): Plan id.
        request (Request): Used to reach the use case.
        days (int): Sample length.
        _ (AdminAccess): The caller.

    Returns:
        PricingInsightOut: The insight.

    Raises:
        HTTPException: 404 if the plan does not exist.
    """
    try:
        result = await request.app.state.plan_pricing_insight_use_case.execute(plan_id=plan_id, now=_now(), days=days)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc
    return PricingInsightOut(
        plan_id=result.plan_id,
        margin_pct=result.margin_pct,
        days=result.days,
        sample=result.sample,
        channels=[ChannelPricingOut(**vars(c)) for c in result.channels],
    )


# --------------------------------------------------------------- cost rates


@router.get("/cost-rates", response_model=list[CostRateOut])
async def list_cost_rates(
    request: Request, _: AdminAccess = Depends(admin_access("cost_rates", "read"))
) -> list[CostRateOut]:
    """The whole cost catalog, every version (admin only).

    Args:
        request (Request): Used to reach the cost rate repository.
        _ (AdminAccess): The caller.

    Returns:
        list[CostRateOut]: The rates.
    """
    return [CostRateOut(**r.model_dump()) for r in await request.app.state.cost_rate_repo.list_all()]


@router.post("/cost-rates", response_model=CostRateOut, status_code=201)
async def create_cost_rate(
    body: CostRateCreate, request: Request, _: AdminAccess = Depends(admin_access("cost_rates", "write"))
) -> CostRateOut:
    """Add a rate, or a new version of a meter's price (admin only).

    Args:
        body (CostRateCreate): The rate; valid from now if not given.
        request (Request): Used to reach the cost rate repository.
        _ (AdminAccess): The caller.

    Returns:
        CostRateOut: The stored rate.
    """
    rate = CostRate(id=uuid4(), **{**body.model_dump(), "valid_from": body.valid_from or _now()})
    return CostRateOut(**(await request.app.state.cost_rate_repo.create(rate)).model_dump())


@router.delete("/cost-rates/{rate_id}", status_code=204)
async def delete_cost_rate(
    rate_id: UUID, request: Request, _: AdminAccess = Depends(admin_access("cost_rates", "write"))
) -> Response:
    """Delete a rate entered by mistake (admin only). To change a price,
    add a new version instead, so past usage keeps its price.

    Args:
        rate_id (UUID): Rate id.
        request (Request): Used to reach the cost rate repository.
        _ (AdminAccess): The caller.

    Returns:
        Response: 204.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    if not await request.app.state.cost_rate_repo.delete(rate_id):
        raise HTTPException(status_code=404, detail="cost rate not found")
    return Response(status_code=204)


@router.get("/cost-rates/unrated", response_model=list[UnratedMeterOut])
async def list_unrated_meters(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    _: AdminAccess = Depends(admin_access("cost_rates", "read")),
) -> list[UnratedMeterOut]:
    """Meters used recently that no rate covers (admin only).

    Args:
        request (Request): Used to reach the use case.
        days (int): Window length.
        _ (AdminAccess): The caller.

    Returns:
        list[UnratedMeterOut]: The meters, largest usage first.
    """
    meters = await request.app.state.list_unrated_meters_use_case.execute(now=_now(), days=days)
    return [UnratedMeterOut(**vars(m)) for m in meters]


# ------------------------------------------------------------ subscriptions


@router.get("/tenants/{tenant_id}/subscription", response_model=SubscriptionOut)
async def get_subscription(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("billing", "read"))
) -> SubscriptionOut:
    """A tenant's subscription.

    Args:
        tenant_id (UUID): Tenant id.
        request (Request): Used to reach the repositories.
        access (AdminAccess): The caller (managers scoped to their tenants).

    Returns:
        SubscriptionOut: The subscription.

    Raises:
        HTTPException: 404 if the tenant is unknown/out of scope or has none.
    """
    await _existing_tenant(request, access, tenant_id)
    subscription = await request.app.state.subscription_repo.get(tenant_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="no subscription")
    plan = await request.app.state.plan_repo.get(subscription.plan_id)
    return _subscription_out(subscription, plan)


def _subscription_out(subscription: TenantSubscription, plan: Plan) -> SubscriptionOut:
    """Build a SubscriptionOut.

    Args:
        subscription (TenantSubscription): The subscription.
        plan (Plan): Its plan.

    Returns:
        SubscriptionOut: The response.
    """
    return SubscriptionOut(
        **subscription.model_dump(),
        plan_code=plan.code,
        plan_name=plan.name,
        effective_overage_mode=subscription.effective_mode(plan),
    )


@router.put("/tenants/{tenant_id}/subscription", response_model=SubscriptionOut)
async def put_subscription(
    tenant_id: UUID,
    body: SubscriptionUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("billing", "write")),
) -> SubscriptionOut:
    """Subscribe a tenant to a plan, or change its plan/overrides (admin only).
    Takes effect on the next message; the month's usage so far counts
    against the new plan.

    Args:
        tenant_id (UUID): Tenant id.
        body (SubscriptionUpdate): Plan and overrides.
        request (Request): Used to reach the repositories.
        access (AdminAccess): The caller.

    Returns:
        SubscriptionOut: The subscription.

    Raises:
        HTTPException: 404 if the tenant is unknown; 400 if the plan does
            not exist or is inactive.
    """
    await _existing_tenant(request, access, tenant_id)
    plan = await request.app.state.plan_repo.get(body.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(status_code=400, detail="plan not found or inactive")
    current = await request.app.state.subscription_repo.get(tenant_id)
    subscription = await request.app.state.subscription_repo.upsert(
        TenantSubscription(
            tenant_id=tenant_id,
            plan_id=body.plan_id,
            overage_mode=body.overage_mode,
            spending_cap_micros=body.spending_cap_micros,
            started_at=current.started_at if current else _now(),
        )
    )
    _invalidate_quota_cache(request, tenant_id)
    return _subscription_out(subscription, plan)


@router.delete("/tenants/{tenant_id}/subscription", status_code=204)
async def delete_subscription(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("billing", "write"))
) -> Response:
    """Remove a tenant's subscription: no limits and no charges from now on
    (admin only).

    Args:
        tenant_id (UUID): Tenant id.
        request (Request): Used to reach the repository.
        access (AdminAccess): The caller.

    Returns:
        Response: 204.

    Raises:
        HTTPException: 404 if the tenant is unknown or has no subscription.
    """
    await _existing_tenant(request, access, tenant_id)
    if not await request.app.state.subscription_repo.delete(tenant_id):
        raise HTTPException(status_code=404, detail="no subscription")
    _invalidate_quota_cache(request, tenant_id)
    return Response(status_code=204)


# --------------------------------------------------------------- statements


@router.get("/tenants/{tenant_id}/statement", response_model=StatementOut)
async def get_statement(
    tenant_id: UUID,
    request: Request,
    period: Optional[str] = Query(default=None, pattern=_PERIOD),
    access: AdminAccess = Depends(admin_access("billing", "read")),
) -> StatementOut:
    """A tenant's statement for a month: frozen if closed, live otherwise.

    Args:
        tenant_id (UUID): Tenant id.
        request (Request): Used to reach the use case.
        period (Optional[str]): "YYYY-MM"; current month if omitted.
        access (AdminAccess): The caller.

    Returns:
        StatementOut: The statement (costs only for admins).

    Raises:
        HTTPException: 404 if the tenant is unknown or out of scope.
    """
    await _existing_tenant(request, access, tenant_id)
    now = _now()
    statement = await request.app.state.compute_statement_use_case.execute(
        tenant_id=tenant_id, period=period or period_of(now), now=now
    )
    return statement_out(statement, with_costs=access.unrestricted)


@router.get("/tenants/{tenant_id}/statements", response_model=list[StatementOut])
async def list_statements(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("billing", "read"))
) -> list[StatementOut]:
    """A tenant's closed statements, newest first.

    Args:
        tenant_id (UUID): Tenant id.
        request (Request): Used to reach the repository.
        access (AdminAccess): The caller.

    Returns:
        list[StatementOut]: The statements (costs only for admins).
    """
    await _existing_tenant(request, access, tenant_id)
    statements = await request.app.state.statement_repo.list_by_tenant(tenant_id)
    return [statement_out(s, with_costs=access.unrestricted) for s in statements]


@router.post("/billing/periods/{period}/close", response_model=ClosePeriodOut)
async def close_period(
    period: str, request: Request, _: AdminAccess = Depends(admin_access("billing", "write"))
) -> ClosePeriodOut:
    """Freeze every subscribed tenant's statement for a finished month
    (admin only; the usage worker also does it automatically). Idempotent.

    Args:
        period (str): "YYYY-MM".
        request (Request): Used to reach the use case.
        _ (AdminAccess): The caller.

    Returns:
        ClosePeriodOut: How many statements were closed now.

    Raises:
        HTTPException: 400 if the period is malformed or not over yet.
    """
    try:
        month_bounds(period)
        closed = await request.app.state.close_billing_period_use_case.execute(period=period, now=_now())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ClosePeriodOut(period=period, closed=closed)
