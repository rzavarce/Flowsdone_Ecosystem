"""Tests for the access-control policy and principals."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.auth_dto import AuthenticatedUser, TenantRef
from app.application.services.access_control import (
    POLICY,
    AccessControl,
    AccessDeniedError,
    InvalidReferenceError,
    Principal,
    ResourceNotFoundError,
)
from api_gateway.tests.support.admin_world import World

pytestmark = pytest.mark.anyio


def _principal(role, tenant_ids=None):
    return Principal(role=role, tenant_ids=None if tenant_ids is None else frozenset(tenant_ids))


def test_policy_covers_every_resource_with_read_and_write():
    assert set(POLICY) == {
        "tenants", "projects", "agents", "workflows", "channel_connections",
        "channel_apps", "users", "langflow", "tenant_billing",
        "conversations", "plans", "cost_rates", "billing",
    }
    for actions in POLICY.values():
        assert set(actions) == {"read", "write"}


def test_write_permission_never_exceeds_read_permission():
    # Quien puede escribir un recurso también debe poder leerlo.
    for resource, actions in POLICY.items():
        assert actions["write"] <= actions["read"], resource


@pytest.mark.parametrize("role", ["client", "consultant"])
def test_client_side_roles_appear_nowhere_in_the_policy(role):
    # client y consultant no tocan el admin API en absoluto (ver /me/billing-profile
    # para el equivalente de solo lectura de un client sobre su propio tenant).
    assert all(role not in roles for actions in POLICY.values() for roles in actions.values())


def test_only_admin_touches_global_resources():
    for resource in ("channel_apps", "users"):
        assert POLICY[resource]["read"] == {"admin"} == POLICY[resource]["write"]
    assert POLICY["tenants"]["write"] == {"admin"}


@pytest.mark.parametrize("role,resource,action,allowed", [
    ("botmaster", "agents", "write", True),
    ("botmaster", "workflows", "write", False),
    ("botmaster", "channel_connections", "read", True),
    ("botmaster", "channel_connections", "write", True),
    # Editor de Langflow: cualquier staff (aceptado a sabiendas - ver comentario en POLICY).
    ("botmaster", "langflow", "read", True),
    ("tenant_manager", "langflow", "write", True),
    ("botmaster", "tenant_billing", "read", False),  # gestiona agentes/canales, no facturación
    ("tenant_manager", "tenant_billing", "write", True),
    ("tenant_manager", "projects", "write", True),
    ("tenant_manager", "tenants", "write", False),
    ("client", "tenants", "read", False),
])
def test_authorize_by_role(role, resource, action, allowed):
    if allowed:
        AccessControl.authorize(_principal(role), resource, action)
    else:
        with pytest.raises(AccessDeniedError):
            AccessControl.authorize(_principal(role), resource, action)


def test_machine_principal_is_an_unrestricted_admin():
    p = Principal.machine()
    assert p.role == "admin" and p.unrestricted and p.user_id is None
    assert p.can_see_tenant(uuid4())


def test_from_user_scopes_non_admins_to_their_tenants_and_leaves_admins_unrestricted():
    a, b = uuid4(), uuid4()

    def user(role, tenants):
        return AuthenticatedUser(id=uuid4(), email="x@y.co", name="X", role=role,
                                 tenants=[TenantRef(id=t, name="t") for t in tenants])

    manager = Principal.from_user(user("tenant_manager", [a]))
    assert manager.can_see_tenant(a) and not manager.can_see_tenant(b) and not manager.unrestricted
    assert Principal.from_user(user("admin", [a, b])).unrestricted  # admin: todos, aunque la lista sea parcial


def test_a_user_without_tenants_sees_nothing():
    p = _principal("tenant_manager", [])
    assert not p.unrestricted and not p.can_see_tenant(uuid4())


async def test_ensure_project_distinguishes_nothing_between_missing_and_foreign():
    w = World.build()
    ac = AccessControl(project_repo=w.projects, agent_repo=w.agents)
    manager = _principal("tenant_manager", [w.tenant_a.id])

    assert (await ac.ensure_project(manager, w.project_a.id)).id == w.project_a.id
    for target in (w.project_b.id, uuid4()):
        with pytest.raises(ResourceNotFoundError) as exc:
            await ac.ensure_project(manager, target, resource="agent")
        assert str(exc.value) == "agent not found"


async def test_list_scoped_unions_the_callers_tenants_and_rejects_foreign_filters():
    w = World.build()
    ac = AccessControl(project_repo=w.projects, agent_repo=w.agents)
    both = _principal("tenant_manager", [w.tenant_a.id, w.tenant_b.id])
    only_a = _principal("tenant_manager", [w.tenant_a.id])

    assert len(await ac.list_scoped(both, w.agents.list_by_project, None, resource="project")) == 2
    assert [a.id for a in await ac.list_scoped(only_a, w.agents.list_by_project, None, resource="project")] == [w.agent_a.id]
    with pytest.raises(ResourceNotFoundError):
        await ac.list_scoped(only_a, w.agents.list_by_project, w.project_b.id, resource="project")


async def test_ensure_agent_in_project():
    w = World.build()
    ac = AccessControl(project_repo=w.projects, agent_repo=w.agents)
    await ac.ensure_agent_in_project(w.agent_a.id, w.project_a.id)
    for agent_id in (w.agent_b.id, uuid4()):
        with pytest.raises(InvalidReferenceError):
            await ac.ensure_agent_in_project(agent_id, w.project_a.id)
