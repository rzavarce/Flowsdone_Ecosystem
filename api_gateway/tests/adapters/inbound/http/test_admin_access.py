"""Authorization of the admin API: authentication, role matrix, tenant
isolation, cross-tenant references, CSRF and user management.

Runs the real routers/dependencies/use cases over ASGI with in-memory
persistence (see support/admin_world.py).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import settings
from api_gateway.tests.support.admin_world import CSRF, World, cookie

pytestmark = pytest.mark.anyio

BASE = "/internal/admin"


async def _call(client, method, path, *, token=None, api_key=None, json=None, csrf=True):
    headers = {}
    if token:
        headers.update(cookie(token))
    if api_key is not None:
        headers["X-Admin-Api-Key"] = api_key
    if csrf:
        headers.update(CSRF)
    return await client.request(method, BASE + path, headers=headers, json=json)


def _new_tenant(**over):
    # A tenant always ships with its `client` user (see CreateTenantUseCase).
    body = {"name": "N", "slug": "n", "client_email": "n@cliente.com", "client_name": "N Cliente"}
    body.update(over)
    return body


@pytest.fixture
def world():
    return World.build()


# ------------------------------------------------------------ authentication


async def test_no_credentials_is_401(world):
    async with world.client() as c:
        for path in ("/tenants", "/projects", "/agents", "/channel-connections", "/users"):
            assert (await _call(c, "GET", path)).status_code == 401


async def test_invalid_session_cookie_is_401(world):
    async with world.client() as c:
        assert (await _call(c, "GET", "/tenants", token="garbage")).status_code == 401


async def test_api_key_still_grants_full_unrestricted_access(world):
    async with world.client() as c:
        resp = await _call(c, "GET", "/tenants", api_key=settings.ADMIN_API_KEY)
        assert resp.status_code == 200 and len(resp.json()) == 2  # ve todos los tenants
        assert (await _call(c, "GET", "/users", api_key=settings.ADMIN_API_KEY)).status_code == 200
        created = await _call(c, "POST", "/tenants", api_key=settings.ADMIN_API_KEY, json=_new_tenant())
        assert created.status_code == 201


async def test_wrong_api_key_is_rejected_even_with_a_valid_session(world):
    token = await world.token("admin")
    async with world.client() as c:
        resp = await _call(c, "GET", "/tenants", token=token, api_key="wrong")
    assert resp.status_code == 401  # no se "degrada" a la cookie


async def test_api_key_callers_do_not_need_the_csrf_header(world):
    async with world.client() as c:
        resp = await _call(c, "POST", "/tenants", api_key=settings.ADMIN_API_KEY,
                           json=_new_tenant(), csrf=False)
    assert resp.status_code == 201


# -------------------------------------------------------------------- CSRF


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/tenants", _new_tenant()),
    ("PATCH", "/tenants/{a}", {"name": "N"}),
    ("DELETE", "/tenants/{a}", None),
])
async def test_cookie_requests_that_change_state_need_the_csrf_header(world, method, path, body):
    token = await world.token("admin")
    async with world.client() as c:
        resp = await _call(c, method, path.format(a=world.tenant_a.id), token=token, json=body, csrf=False)
    assert resp.status_code == 403 and resp.json()["detail"] == "missing CSRF header"


async def test_a_wrong_csrf_value_is_rejected_and_reads_do_not_need_it(world):
    token = await world.token("admin")
    async with world.client() as c:
        bad = await c.post(BASE + "/tenants", headers={**cookie(token), "X-Requested-With": "XMLHttpRequest"},
                           json=_new_tenant())
        read = await _call(c, "GET", "/tenants", token=token, csrf=False)
    assert bad.status_code == 403
    assert read.status_code == 200


# --------------------------------------------------------------- role matrix

_A = "{a}"


def _matrix():
    """(role, method, path, body-builder, expected status)."""
    rows = []
    def add(method, path, body, allowed_status, allowed_roles, denied_status=403):
        for role in ("admin", "tenant_manager", "botmaster", "client"):
            rows.append((role, method, path, body, allowed_status if role in allowed_roles else denied_status))

    staff = {"admin", "tenant_manager", "botmaster"}
    managers = {"admin", "tenant_manager"}
    add("GET", "/tenants", None, 200, staff)
    add("POST", "/tenants", lambda w: _new_tenant(), 201, {"admin"})
    add("GET", "/projects", None, 200, staff)
    add("POST", "/projects", lambda w: {"tenant_id": str(w.tenant_a.id), "name": "P", "slug": "p"}, 201, managers)
    add("GET", "/agents", None, 200, staff)
    add("POST", "/agents", lambda w: {"project_id": str(w.project_a.id), "name": "A", "langflow_flow_id": "f"}, 201, staff)
    add("GET", "/workflows", None, 200, staff)
    add("POST", "/workflows", lambda w: {"project_id": str(w.project_a.id), "name": "W", "n8n_workflow_id": "n"}, 201, managers)
    # botmaster ahora también gestiona canales de sus tenants (POLICY).
    add("GET", "/channel-connections", None, 200, staff)
    add("POST", "/channel-connections",
        lambda w: {"project_id": str(w.project_a.id), "agent_id": str(w.agent_a.id), "channel_type": "telegram", "external_id": "x"},
        201, staff)
    add("GET", "/channel-apps", None, 200, {"admin"})
    add("GET", "/users", None, 200, {"admin"})
    return rows


@pytest.mark.parametrize("role,method,path,body,expected", _matrix())
async def test_role_matrix(world, role, method, path, body, expected):
    token = await world.token(role)
    async with world.client() as c:
        resp = await _call(c, method, path, token=token, json=body(world) if body else None)
    assert resp.status_code == expected, resp.text


@pytest.mark.parametrize("role", ["tenant_manager", "botmaster", "client"])
async def test_only_admins_can_reveal_or_change_the_shared_provider_credentials(world, role):
    """channel-apps are global secrets of the whole SaaS: never for tenant-scoped roles."""
    token = await world.token(role)
    async with world.client() as c:
        reveal = await _call(c, "GET", "/channel-apps/meta/credentials", token=token)
        write = await _call(c, "PUT", "/channel-apps/meta", token=token, json={"credentials": {"x": "y"}})
        delete = await _call(c, "DELETE", "/channel-apps/meta", token=token)
    assert reveal.status_code == write.status_code == delete.status_code == 403


@pytest.mark.parametrize("role", ["client", "consultant"])
async def test_client_side_roles_cannot_use_the_admin_api_at_all(world, role):
    token = await world.token(role)
    async with world.client() as c:
        for path in ("/tenants", "/projects", "/agents", "/workflows", "/channel-connections", "/channel-apps", "/users"):
            assert (await _call(c, "GET", path, token=token)).status_code == 403, path
        billing = f"/tenants/{world.tenant_a.id}/billing"
        assert (await _call(c, "GET", billing, token=token)).status_code == 403


async def test_tenant_billing_managers_read_and_write_scoped_to_their_tenants(world):
    path_a = f"/tenants/{world.tenant_a.id}/billing"
    path_b = f"/tenants/{world.tenant_b.id}/billing"
    admin_token = await world.token("admin")
    manager_token = await world.token("tenant_manager")  # scoped to tenant_a (ver admin_world.py)
    botmaster_token = await world.token("botmaster")

    async with world.client() as c:
        empty = await _call(c, "GET", path_a, token=admin_token)
        assert empty.status_code == 200
        assert empty.json()["legal_name"] is None  # nada cargado todavía, no 404

        updated = await _call(c, "PUT", path_a, token=admin_token, json={
            "legal_name": "Clínica Vital S.A.", "tax_id": "RFC123", "billing_email": "facturas@vital.com",
            "currency": "MXN", "plan": "pro",
        })
        assert updated.status_code == 200
        body = updated.json()
        assert body["legal_name"] == "Clínica Vital S.A." and body["currency"] == "MXN" and body["plan"] == "pro"

        again = await _call(c, "GET", path_a, token=manager_token)  # el gestor también puede leerlo
        assert again.status_code == 200 and again.json()["legal_name"] == "Clínica Vital S.A."

        out_of_scope = await _call(c, "GET", path_b, token=manager_token)
        assert out_of_scope.status_code == 404  # tenant_b no es suyo

        forbidden = await _call(c, "GET", path_a, token=botmaster_token)
        assert forbidden.status_code == 403  # botmaster gestiona agentes/canales, no facturación

        unknown_tenant = await _call(c, "GET", f"/tenants/{uuid4()}/billing", token=admin_token)
        assert unknown_tenant.status_code == 404


# ------------------------------------------------------- tenant isolation


async def test_manager_only_sees_their_own_tenant_and_admin_sees_all(world):
    async with world.client() as c:
        mine = await _call(c, "GET", "/tenants", token=await world.token("tenant_manager"))
        everything = await _call(c, "GET", "/tenants", token=await world.token("admin"))
    assert [t["slug"] for t in mine.json()] == ["a"]
    assert {t["slug"] for t in everything.json()} == {"a", "b"}


async def test_out_of_scope_tenant_is_404_and_indistinguishable_from_missing(world):
    token = await world.token("tenant_manager")
    async with world.client() as c:
        other = await _call(c, "GET", f"/tenants/{world.tenant_b.id}", token=token)
        missing = await _call(c, "GET", f"/tenants/{uuid4()}", token=token)
        own = await _call(c, "GET", f"/tenants/{world.tenant_a.id}", token=token)
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()
    assert own.status_code == 200


async def test_projects_are_isolated_by_tenant(world):
    token = await world.token("tenant_manager")
    async with world.client() as c:
        listed = await _call(c, "GET", "/projects", token=token)
        by_other_tenant = await _call(c, "GET", f"/projects?tenant_id={world.tenant_b.id}", token=token)
        get_other = await _call(c, "GET", f"/projects/{world.project_b.id}", token=token)
        patch_other = await _call(c, "PATCH", f"/projects/{world.project_b.id}", token=token, json={"name": "hacked"})
        delete_other = await _call(c, "DELETE", f"/projects/{world.project_b.id}", token=token)
        create_in_other = await _call(c, "POST", "/projects", token=token,
                                      json={"tenant_id": str(world.tenant_b.id), "name": "X", "slug": "x"})
    assert [p["name"] for p in listed.json()] == ["PA"]
    assert by_other_tenant.status_code == get_other.status_code == patch_other.status_code == 404
    assert delete_other.status_code == create_in_other.status_code == 404
    # y nada cambió en el tenant ajeno
    assert world.projects.items[world.project_b.id].name == "PB"


@pytest.mark.parametrize("resource,repo,mine,theirs,patch", [
    ("agents", "agents", "agent_a", "agent_b", {"name": "hacked"}),
    ("workflows", "workflows", "workflow_a", "workflow_b", {"name": "hacked"}),
    ("channel-connections", "connections", "conn_a", "conn_b", {"display_name": "hacked"}),
])
async def test_project_owned_resources_are_isolated_by_tenant(world, resource, repo, mine, theirs, patch):
    mine_item, their_item = getattr(world, mine), getattr(world, theirs)
    token = await world.token("tenant_manager")
    async with world.client() as c:
        listed = await _call(c, "GET", f"/{resource}", token=token)
        filtered_other = await _call(c, "GET", f"/{resource}?project_id={world.project_b.id}", token=token)
        get_mine = await _call(c, "GET", f"/{resource}/{mine_item.id}", token=token)
        get_theirs = await _call(c, "GET", f"/{resource}/{their_item.id}", token=token)
        patch_theirs = await _call(c, "PATCH", f"/{resource}/{their_item.id}", token=token, json=patch)
        delete_theirs = await _call(c, "DELETE", f"/{resource}/{their_item.id}", token=token)

    assert [i["id"] for i in listed.json()] == [str(mine_item.id)]  # sin filtro: solo lo suyo
    assert filtered_other.status_code == 404
    assert get_mine.status_code == 200
    assert get_theirs.status_code == patch_theirs.status_code == delete_theirs.status_code == 404
    assert their_item.id in getattr(world, repo).items  # no se borró
    assert getattr(world, repo).items[their_item.id] == their_item  # ni se modificó


async def test_creating_in_another_tenants_project_is_404(world):
    token = await world.token("tenant_manager")
    async with world.client() as c:
        agent = await _call(c, "POST", "/agents", token=token,
                            json={"project_id": str(world.project_b.id), "name": "X", "langflow_flow_id": "f"})
        wf = await _call(c, "POST", "/workflows", token=token,
                         json={"project_id": str(world.project_b.id), "name": "X", "n8n_workflow_id": "n"})
    assert agent.status_code == wf.status_code == 404
    assert len(world.agents.items) == 2 and len(world.workflows.items) == 2


async def test_admin_can_reach_every_tenants_resources(world):
    token = await world.token("admin")
    async with world.client() as c:
        assert (await _call(c, "GET", f"/agents/{world.agent_b.id}", token=token)).status_code == 200
        assert len((await _call(c, "GET", "/agents", token=token)).json()) == 2


async def test_botmaster_edits_agents_of_their_tenant_only(world):
    token = await world.token("botmaster")
    async with world.client() as c:
        ok = await _call(c, "PATCH", f"/agents/{world.agent_a.id}", token=token, json={"name": "renamed"})
        foreign = await _call(c, "PATCH", f"/agents/{world.agent_b.id}", token=token, json={"name": "hacked"})
        wf_write = await _call(c, "PATCH", f"/workflows/{world.workflow_a.id}", token=token, json={"name": "x"})
    assert ok.status_code == 200 and ok.json()["name"] == "renamed"
    assert foreign.status_code == 404
    assert wf_write.status_code == 403  # workflows: solo lectura para botmaster


# ------------------------------------------------ cross-tenant agent reference


async def test_channel_cannot_be_bound_to_another_tenants_agent_on_create(world):
    token = await world.token("tenant_manager")
    async with world.client() as c:
        resp = await _call(c, "POST", "/channel-connections", token=token, json={
            "project_id": str(world.project_a.id), "agent_id": str(world.agent_b.id),
            "channel_type": "telegram", "external_id": "steal",
        })
    assert resp.status_code == 400
    assert len(world.connections.items) == 2


async def test_channel_cannot_be_rebound_to_another_tenants_agent_on_update(world):
    token = await world.token("tenant_manager")
    async with world.client() as c:
        steal = await _call(c, "PATCH", f"/channel-connections/{world.conn_a.id}", token=token,
                            json={"agent_id": str(world.agent_b.id)})
        unknown = await _call(c, "PATCH", f"/channel-connections/{world.conn_a.id}", token=token,
                              json={"agent_id": str(uuid4())})
    assert steal.status_code == unknown.status_code == 400
    assert world.connections.items[world.conn_a.id].agent_id == world.agent_a.id


async def test_channel_can_be_rebound_to_another_agent_of_the_same_project(world):
    second = await world.agents.create(project_id=world.project_a.id, name="AA2", langflow_flow_id="f2")
    token = await world.token("tenant_manager")
    async with world.client() as c:
        resp = await _call(c, "PATCH", f"/channel-connections/{world.conn_a.id}", token=token,
                           json={"agent_id": str(second.id)})
    assert resp.status_code == 200 and resp.json()["agent_id"] == str(second.id)


async def test_api_key_is_also_subject_to_the_agent_project_check(world):
    async with world.client() as c:
        resp = await _call(c, "POST", "/channel-connections", api_key=settings.ADMIN_API_KEY, json={
            "project_id": str(world.project_a.id), "agent_id": str(world.agent_b.id),
            "channel_type": "telegram", "external_id": "x",
        })
    assert resp.status_code == 400


# --------------------------------------------------------- user management


def _new_user(world, **over):
    # No password: users are created pending and activate via the emailed
    # link (see ProvisionUserUseCase) - nobody sets it at creation anymore.
    body = {"email": "New@Empresa.com", "name": "Nueva", "role": "client",
            "tenant_ids": [str(world.tenant_a.id)]}
    body.update(over)
    return body


async def test_admin_creates_lists_and_reads_users_without_hashes(world):
    token = await world.token("admin")
    async with world.client() as c:
        created = await _call(c, "POST", "/users", token=token, json=_new_user(world))
        listed = await _call(c, "GET", "/users", token=token)
        one = await _call(c, "GET", f"/users/{created.json()['id']}", token=token)
    assert created.status_code == 201
    assert created.json()["email"] == "new@empresa.com"
    # Created pending, not active: nobody sets a password at creation time
    # anymore - the user activates via the emailed link.
    assert created.json()["status"] == "pending"
    for resp in (created, one):
        assert "password" not in resp.text and "hash" not in resp.text
    assert len(listed.json()) == 6  # 5 de World (uno por rol, incluido consultant) + el recién creado
    # ProvisionUserUseCase sent the activation email.
    assert world.mailer.sent[-1]["to"] == "new@empresa.com"
    assert world.mailer.sent[-1]["template"] == "account_activation"


async def test_user_creation_validation_and_duplicates(world):
    token = await world.token("admin")
    async with world.client() as c:
        await _call(c, "POST", "/users", token=token, json=_new_user(world))
        dup = await _call(c, "POST", "/users", token=token, json=_new_user(world, email="new@empresa.com"))
        bad_role = await _call(c, "POST", "/users", token=token, json=_new_user(world, email="b@x.com", role="root"))
        no_tenant = await _call(c, "POST", "/users", token=token, json=_new_user(world, email="d@x.com", tenant_ids=[]))
        ghost_tenant = await _call(c, "POST", "/users", token=token,
                                   json=_new_user(world, email="e@x.com", tenant_ids=[str(uuid4())]))
    assert dup.status_code == 409
    assert bad_role.status_code == no_tenant.status_code == ghost_tenant.status_code == 400


async def test_only_admins_manage_users(world):
    async with world.client() as c:
        for role in ("tenant_manager", "botmaster", "client"):
            token = await world.token(role)
            assert (await _call(c, "POST", "/users", token=token, json=_new_user(world))).status_code == 403
            assert (await _call(c, "PATCH", f"/users/{world.by_role['client'].id}", token=token,
                                json={"role": "admin"})).status_code == 403  # sin escalada de privilegios
            assert (await _call(c, "DELETE", f"/users/{world.by_role['client'].id}", token=token)).status_code == 403


async def test_changing_a_users_access_closes_their_sessions_immediately(world):
    victim = world.by_role["client"]
    victim_token = await world.token(victim)
    admin_token = await world.token("admin")
    async with world.client() as c:
        assert (await _call(c, "GET", "/tenants", token=victim_token)).status_code == 403  # autenticado, sin permiso
        resp = await _call(c, "PATCH", f"/users/{victim.id}", token=admin_token, json={"status": "disabled"})
        after = await _call(c, "GET", "/tenants", token=victim_token)
    assert resp.status_code == 200 and resp.json()["status"] == "disabled"
    assert after.status_code == 401  # su sesión ya no existe


async def test_promoting_a_user_takes_effect_on_their_next_request(world):
    user = world.by_role["botmaster"]
    admin_token = await world.token("admin")
    async with world.client() as c:
        promote = await _call(c, "PATCH", f"/users/{user.id}", token=admin_token,
                              json={"role": "tenant_manager", "password": "otra-clave-larga-2"})
    assert promote.status_code == 200 and promote.json()["role"] == "tenant_manager"


async def test_an_admin_cannot_lock_themselves_out(world):
    me = world.by_role["admin"]
    token = await world.token("admin")
    async with world.client() as c:
        disable = await _call(c, "PATCH", f"/users/{me.id}", token=token, json={"status": "disabled"})
        demote = await _call(c, "PATCH", f"/users/{me.id}", token=token, json={"role": "client"})
        delete = await _call(c, "DELETE", f"/users/{me.id}", token=token)
        rename = await _call(c, "PATCH", f"/users/{me.id}", token=token, json={"name": "Nuevo Nombre"})
        still_in = await _call(c, "GET", "/users", token=token)
    assert disable.status_code == demote.status_code == delete.status_code == 409
    assert rename.status_code == 200  # editar otros campos sí
    assert still_in.status_code == 200  # y renombrarse no cierra su sesión


async def test_deleting_a_user_closes_their_sessions_and_404s_when_missing(world):
    victim = world.by_role["botmaster"]
    victim_token = await world.token(victim)
    admin_token = await world.token("admin")
    async with world.client() as c:
        deleted = await _call(c, "DELETE", f"/users/{victim.id}", token=admin_token)
        again = await _call(c, "DELETE", f"/users/{victim.id}", token=admin_token)
        after = await _call(c, "GET", "/agents", token=victim_token)
        get_missing = await _call(c, "GET", f"/users/{uuid4()}", token=admin_token)
    assert deleted.status_code == 204 and again.status_code == 404
    assert after.status_code == 401
    assert get_missing.status_code == 404


async def test_api_key_can_manage_users_and_is_not_subject_to_self_lockout(world):
    async with world.client() as c:
        made = await _call(c, "POST", "/users", api_key=settings.ADMIN_API_KEY, json=_new_user(world))
        deleted = await _call(c, "DELETE", f"/users/{world.by_role['admin'].id}", api_key=settings.ADMIN_API_KEY)
    assert made.status_code == 201 and deleted.status_code == 204


# ------------------------------------------------------ duplicados -> 409 (no 500)


async def test_duplicates_answer_409_instead_of_500(world):
    """La violación UNIQUE de la base llega como AlreadyExistsError y se muestra como 409."""
    token = await world.token("admin")
    conn = {"project_id": str(world.project_a.id), "agent_id": str(world.agent_a.id),
            "channel_type": "whatsapp_evolution", "external_id": "instancia-repetida"}
    async with world.client() as c:
        first = await _call(c, "POST", "/channel-connections", token=token, json=conn)
        again = await _call(c, "POST", "/channel-connections", token=token, json=conn)
        tenant = await _call(c, "POST", "/tenants", token=token,
                            json=_new_tenant(name="Otro A", slug="a", client_email="otro-a@cliente.com"))
        project = await _call(c, "POST", "/projects", token=token,
                              json={"tenant_id": str(world.tenant_a.id), "name": "Otro", "slug": "pa"})
    assert first.status_code == 201
    assert again.status_code == tenant.status_code == project.status_code == 409
    assert again.json() == {"detail": "already exists"}


async def test_the_same_slug_is_fine_in_a_different_tenant(world):
    token = await world.token("admin")
    async with world.client() as c:
        resp = await _call(c, "POST", "/projects", token=token,
                           json={"tenant_id": str(world.tenant_b.id), "name": "Otro", "slug": "pa"})
    assert resp.status_code == 201


# ------------------------------------------------------ user profile & photo

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


async def test_admin_creates_a_user_with_optional_profile_fields(world):
    token = await world.token("admin")
    async with world.client() as c:
        created = await _call(c, "POST", "/users", token=token, json=_new_user(
            world, phone="600 111 222", address="Calle 1", social_links={"website": "https://n.dev"},
        ))
        plain = await _call(c, "POST", "/users", token=token, json=_new_user(world, email="plain@x.com"))
        bad = await _call(c, "POST", "/users", token=token, json=_new_user(
            world, email="bad@x.com", social_links={"website": "nope"},
        ))
    assert created.status_code == 201
    assert created.json()["phone"] == "600 111 222"
    assert created.json()["social_links"] == {"website": "https://n.dev"}
    assert plain.status_code == 201 and plain.json()["phone"] is None
    # Validated before creating: no half-created user left behind.
    assert bad.status_code == 400
    assert not any(u.email == "bad@x.com" for u in world.users.users.values())


async def test_admin_edits_profile_fields_and_photo_of_a_user(world):
    token = await world.token("admin")
    target = world.by_role["client"]
    async with world.client() as c:
        patched = await _call(c, "PATCH", f"/users/{target.id}", token=token, json={"address": "Av. 2"})
        headers = {**cookie(token), **CSRF, "Content-Type": "image/png"}
        put = await c.put(f"{BASE}/users/{target.id}/avatar", headers=headers, content=PNG)
        got = await c.get(f"{BASE}/users/{target.id}/avatar", headers=cookie(token))
        removed = await _call(c, "DELETE", f"/users/{target.id}/avatar", token=token)
        ghost = await c.put(f"{BASE}/users/{uuid4()}/avatar", headers=headers, content=PNG)
    assert patched.json()["address"] == "Av. 2"
    assert put.status_code == 200 and put.json()["avatar_updated_at"]
    assert got.status_code == 200 and got.content == PNG
    assert removed.status_code == 200 and removed.json()["avatar_updated_at"] is None
    assert ghost.status_code == 404


async def test_only_admins_touch_other_users_photos(world):
    target = world.by_role["client"]
    for role in ("tenant_manager", "botmaster", "client"):
        token = await world.token(role)
        async with world.client() as c:
            headers = {**cookie(token), **CSRF}
            assert (await c.put(f"{BASE}/users/{target.id}/avatar", headers=headers, content=PNG)).status_code == 403
            assert (await c.get(f"{BASE}/users/{target.id}/avatar", headers=cookie(token))).status_code == 403
