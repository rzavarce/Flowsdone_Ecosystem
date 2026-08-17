"""Admin HTTP API: tenant/project/agent/workflow/channel CRUD, mounted
under /internal/admin and protected by require_admin_api_key.
"""

from fastapi import APIRouter

from api_gateway.app.adapters.inbound.http.admin.agents import router as agents_router
from api_gateway.app.adapters.inbound.http.admin.channel_apps import router as channel_apps_router
from api_gateway.app.adapters.inbound.http.admin.channel_connections import router as channel_connections_router
from api_gateway.app.adapters.inbound.http.admin.projects import router as projects_router
from api_gateway.app.adapters.inbound.http.admin.tenants import router as tenants_router
from api_gateway.app.adapters.inbound.http.admin.workflows import router as workflows_router

router = APIRouter(prefix="/internal/admin")

for _sub_router in (
    tenants_router,
    projects_router,
    agents_router,
    workflows_router,
    channel_connections_router,
    channel_apps_router,
):
    router.include_router(_sub_router)
