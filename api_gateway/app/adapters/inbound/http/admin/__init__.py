"""Admin HTTP API: tenant/project/agent/workflow/channel/user CRUD, mounted
under /internal/admin.

Callers authenticate with either the shared `X-Admin-Api-Key` (machines) or a
console session cookie (people). Each route declares the resource and action it
needs via `admin_access(...)`; see `access.py` and `application/services/access_control.py`
for the role matrix and tenant scoping.
"""

from fastapi import APIRouter

from app.adapters.inbound.http.admin.agents import router as agents_router
from app.adapters.inbound.http.admin.channel_apps import router as channel_apps_router
from app.adapters.inbound.http.admin.channel_connections import router as channel_connections_router
from app.adapters.inbound.http.admin.langflow import router as langflow_router
from app.adapters.inbound.http.admin.projects import router as projects_router
from app.adapters.inbound.http.admin.tenant_billing import router as tenant_billing_router
from app.adapters.inbound.http.admin.tenants import router as tenants_router
from app.adapters.inbound.http.admin.users import router as users_router
from app.adapters.inbound.http.admin.workflows import router as workflows_router

router = APIRouter(prefix="/internal/admin")

for _sub_router in (
    tenants_router,
    tenant_billing_router,
    projects_router,
    agents_router,
    workflows_router,
    channel_connections_router,
    channel_apps_router,
    users_router,
    langflow_router,
):
    router.include_router(_sub_router)
