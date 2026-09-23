"""Self-service endpoints for the signed-in user's own data.

Unlike `/internal/admin/*`, these never go through `POLICY`/`AccessControl`:
they only ever act on the caller's own session, so there is nothing to scope
by role - any signed-in user (client and consultant included, who otherwise
never touch the admin API at all) can call them. Keep this router for data
that is inherently "about me", not a general-purpose escape hatch around
`POLICY`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.schemas import TenantBillingOut
from app.adapters.inbound.http.auth_deps import get_current_user
from app.application.dto.auth_dto import AuthenticatedUser

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/billing-profile", response_model=TenantBillingOut)
async def my_billing_profile(
    request: Request, user: AuthenticatedUser = Depends(get_current_user)
) -> TenantBillingOut:
    """Billing/company data of the caller's own tenant (read-only).

    Built for `client` (see `TenantBillingProfile`): the tenant is whichever
    one the caller belongs to, resolved from the session - never a path
    parameter, so there is no tenant to scope-check.

    Args:
        request (Request): Used to reach `request.app.state.tenant_billing_profile_repo`.
        user (AuthenticatedUser): The signed-in user.

    Returns:
        TenantBillingOut: The profile - all fields `None` if nothing was
        filled in yet.

    Raises:
        HTTPException: 404 if the caller belongs to no tenant (shouldn't
            happen for `client`/`consultant` in practice, but `admin` has
            none by design and would hit this too).
    """
    if not user.tenants:
        raise HTTPException(status_code=404, detail="no tenant for this account")
    tenant_id = user.tenants[0].id
    repo = request.app.state.tenant_billing_profile_repo
    profile = await repo.get_by_tenant_id(tenant_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="no billing profile yet")
    return TenantBillingOut(**profile.model_dump())
