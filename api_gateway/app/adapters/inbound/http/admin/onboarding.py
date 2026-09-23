"""Admin endpoint with a tenant's onboarding checklist (new-client wizard)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import OnboardingCheckOut, OnboardingOut

router = APIRouter(prefix="/tenants", tags=["admin:onboarding"])


@router.get("/{tenant_id}/onboarding", response_model=OnboardingOut)
async def get_onboarding(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("billing", "read"))
) -> OnboardingOut:
    """Where a tenant's onboarding stands: the checklist (billing data,
    client account, plan, project, default agent and its flow, OpenAI key
    variable, channels) and the first wizard step still to do.

    Args:
        tenant_id (UUID): The tenant.
        request (Request): Used to reach the use case and the tenant repository.
        access (AdminAccess): The caller (admin/tenant_manager, own tenants).

    Returns:
        OnboardingOut: The status.

    Raises:
        HTTPException: 404 if the tenant does not exist or is out of scope.
    """
    access.tenant(tenant_id)
    if not await request.app.state.tenant_repo.get_by_id(tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")
    status = await request.app.state.get_onboarding_status_use_case.execute(tenant_id)
    return OnboardingOut(
        tenant_id=status.tenant_id,
        next_step=status.next_step,
        project_id=status.project_id,
        checks=[OnboardingCheckOut(**vars(c)) for c in status.checks],
    )
