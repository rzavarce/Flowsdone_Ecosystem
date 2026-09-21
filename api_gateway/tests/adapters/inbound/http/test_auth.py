"""Tests for the console auth router (/auth) and its dependencies."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends

from app.adapters.inbound.http.auth import router
from app.adapters.inbound.http.auth_deps import ensure_tenant_access, get_current_user, require_roles
from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases.authenticate_user import AuthenticateUserUseCase
from app.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.logout_user import LogoutUserUseCase
from app.core.config import settings
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakeLoginThrottle,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio

PASSWORD = "correct-horse-battery"
COOKIE = settings.AUTH_COOKIE_NAME


def _state(users=(), tenants=(), max_email=3, max_ip=50):
    user_repo = FakeUserRepo()
    for u in users:
        user_repo.add(u, PASSWORD)
    tenant_repo = FakeTenantRepo(list(tenants))
    sessions = FakeAuthSessionRepo()
    return dict(
        sessions=sessions,
        authenticate_user_use_case=AuthenticateUserUseCase(
            user_repo=user_repo,
            tenant_repo=tenant_repo,
            hasher=FakePasswordHasher(),
            sessions=sessions,
            throttle=FakeLoginThrottle(),
            session_ttl_seconds=3600,
            window_seconds=900,
            max_failures_per_email=max_email,
            max_failures_per_ip=max_ip,
        ),
        get_current_user_use_case=GetCurrentUserUseCase(
            sessions=sessions, user_repo=user_repo, tenant_repo=tenant_repo, session_ttl_seconds=3600
        ),
        logout_user_use_case=LogoutUserUseCase(sessions=sessions),
    )


def _login(client, email, password=PASSWORD, **headers):
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers)


def _cookie(token):
    return {"Cookie": f"{COOKIE}={token}"}


async def test_login_returns_the_user_and_sets_a_hardened_cookie():
    tenant = make_tenant()
    user = make_user(role="tenant_manager", tenant_ids=[tenant.id])
    async with client_for_router(router, **_state([user], [tenant])) as client:
        resp = await _login(client, user.email)

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user.email and body["role"] == "tenant_manager"
    assert body["tenants"] == [{"id": str(tenant.id), "name": tenant.name}]
    assert "password" not in body and "password_hash" not in body

    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert f"Max-Age={settings.AUTH_SESSION_TTL_SECONDS}" in cookie
    assert resp.headers["cache-control"] == "no-store"


async def test_cookie_is_secure_only_when_the_public_url_is_https(monkeypatch):
    user = make_user()
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", None)

    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000")
    async with client_for_router(router, **_state([user])) as client:
        assert "Secure" not in (await _login(client, user.email)).headers["set-cookie"]

    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://api.flowsdone.com")
    async with client_for_router(router, **_state([user])) as client:
        assert "Secure" in (await _login(client, user.email)).headers["set-cookie"]

    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", False)  # override explícito
    async with client_for_router(router, **_state([user])) as client:
        assert "Secure" not in (await _login(client, user.email)).headers["set-cookie"]


async def test_wrong_password_and_unknown_email_look_identical():
    user = make_user()
    async with client_for_router(router, **_state([user])) as client:
        wrong = await _login(client, user.email, "bad")
        unknown = await _login(client, "ghost@x.com")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers


async def test_disabled_account_gets_the_same_401():
    user = make_user(status="disabled")
    async with client_for_router(router, **_state([user])) as client:
        resp = await _login(client, user.email)
    assert resp.status_code == 401 and resp.json() == {"detail": "invalid credentials"}


async def test_throttled_login_answers_429_with_retry_after_and_no_cookie():
    user = make_user()
    async with client_for_router(router, **_state([user], max_email=2)) as client:
        for _ in range(2):
            assert (await _login(client, user.email, "bad")).status_code == 401
        resp = await _login(client, user.email)  # incluso con la clave correcta

    assert resp.status_code == 429
    assert resp.headers["retry-after"] == str(settings.AUTH_LOGIN_WINDOW_SECONDS)
    assert "set-cookie" not in resp.headers


async def test_client_ip_comes_from_the_first_forwarded_hop(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TRUST_FORWARDED_FOR", True)
    state = _state(max_ip=1)
    async with client_for_router(router, **state) as client:
        await _login(client, "ghost@x.com", "bad", **{"X-Forwarded-For": "8.8.8.8, 10.0.0.1"})
        blocked = await _login(client, "other@x.com", "bad", **{"X-Forwarded-For": "8.8.8.8"})
        elsewhere = await _login(client, "other@x.com", "bad", **{"X-Forwarded-For": "1.1.1.1"})

    assert blocked.status_code == 429
    assert elsewhere.status_code == 401


async def test_forwarded_for_is_ignored_when_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TRUST_FORWARDED_FOR", False)
    async with client_for_router(router, **_state(max_ip=1)) as client:
        await _login(client, "ghost@x.com", "bad", **{"X-Forwarded-For": "8.8.8.8"})
        # Otra IP declarada, pero se usa la del socket (la misma): queda bloqueada.
        resp = await _login(client, "other@x.com", "bad", **{"X-Forwarded-For": "1.1.1.1"})
    assert resp.status_code == 429


@pytest.mark.parametrize(
    "payload", [{}, {"email": "a@x.com"}, {"email": "", "password": "x"}, {"email": "a@x.com", "password": ""},
                {"email": "a@x.com", "password": "x" * 2000}]
)
async def test_login_validates_the_body(payload):
    async with client_for_router(router, **_state()) as client:
        resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 422


async def test_me_without_a_session_is_401():
    async with client_for_router(router, **_state()) as client:
        assert (await client.get("/auth/me")).status_code == 401
        assert (await client.get("/auth/me", headers=_cookie("garbage"))).status_code == 401


async def test_me_returns_the_user_and_renews_the_cookie():
    user = make_user()
    async with client_for_router(router, **_state([user])) as client:
        token = (await _login(client, user.email)).headers["set-cookie"].split(";")[0].split("=", 1)[1]
        resp = await client.get("/auth/me", headers=_cookie(token))

    assert resp.status_code == 200 and resp.json()["email"] == user.email
    assert resp.headers["set-cookie"].startswith(f"{COOKIE}={token}")
    assert resp.headers["cache-control"] == "no-store"


async def test_logout_invalidates_the_session_and_clears_the_cookie():
    user = make_user()
    state = _state([user])
    async with client_for_router(router, **state) as client:
        token = (await _login(client, user.email)).headers["set-cookie"].split(";")[0].split("=", 1)[1]

        out = await client.post("/auth/logout", headers=_cookie(token))
        after = await client.get("/auth/me", headers=_cookie(token))

    assert out.status_code == 204
    assert "Max-Age=0" in out.headers["set-cookie"] or 'expires=' in out.headers["set-cookie"].lower()
    assert after.status_code == 401  # aunque alguien conserve la cookie, ya no sirve
    assert state["sessions"].sessions == {}


async def test_logout_is_idempotent_without_a_session():
    async with client_for_router(router, **_state()) as client:
        assert (await client.post("/auth/logout")).status_code == 204


async def test_a_user_disabled_after_login_loses_access_immediately():
    user = make_user()
    state = _state([user])
    async with client_for_router(router, **state) as client:
        token = (await _login(client, user.email)).headers["set-cookie"].split(";")[0].split("=", 1)[1]
        assert (await client.get("/auth/me", headers=_cookie(token))).status_code == 200

        # Un admin deshabilita la cuenta: la próxima request ya falla.
        repo = state["get_current_user_use_case"]._user_repo
        repo.users[user.id] = make_user(id=user.id, email=user.email, status="disabled")
        assert (await client.get("/auth/me", headers=_cookie(token))).status_code == 401


# --------------------------- dependencias reutilizables ---------------------------


def _protected_router():
    r = APIRouter()

    @r.get("/whoami")
    async def whoami(user: AuthenticatedUser = Depends(get_current_user)):
        return {"role": user.role}

    @r.get("/admin-only")
    async def admin_only(user: AuthenticatedUser = Depends(require_roles("admin"))):
        return {"ok": True}

    @r.get("/managers")
    async def managers(user: AuthenticatedUser = Depends(require_roles("admin", "tenant_manager"))):
        return {"ok": True}

    @r.get("/tenants/{tenant_id}")
    async def tenant(tenant_id: str, user: AuthenticatedUser = Depends(get_current_user)):
        from uuid import UUID

        ensure_tenant_access(user, UUID(tenant_id))
        return {"ok": True}

    return r


async def _token_for(client, user):
    resp = await _login(client, user.email)
    return resp.headers["set-cookie"].split(";")[0].split("=", 1)[1]


async def test_require_roles_401_without_session_403_for_wrong_role_200_for_allowed():
    admin = make_user(email="a@x.com", role="admin")
    client_user = make_user(email="c@x.com", role="client", tenant_ids=[uuid4()])
    state = _state([admin, client_user])
    async with client_for_router(_protected_router(), **state) as http, client_for_router(router, **state) as auth:
        admin_t, client_t = await _token_for(auth, admin), await _token_for(auth, client_user)

        assert (await http.get("/admin-only")).status_code == 401
        assert (await http.get("/admin-only", headers=_cookie(client_t))).status_code == 403
        assert (await http.get("/admin-only", headers=_cookie(admin_t))).status_code == 200
        assert (await http.get("/managers", headers=_cookie(client_t))).status_code == 403
        assert (await http.get("/whoami", headers=_cookie(client_t))).json() == {"role": "client"}


async def test_ensure_tenant_access_admin_any_member_own_others_denied():
    mine, other = make_tenant(slug="mine"), make_tenant(slug="other")
    admin = make_user(email="a@x.com", role="admin")
    manager = make_user(email="m@x.com", role="tenant_manager", tenant_ids=[mine.id])
    state = _state([admin, manager], [mine, other])
    async with client_for_router(_protected_router(), **state) as http, client_for_router(router, **state) as auth:
        admin_t, manager_t = await _token_for(auth, admin), await _token_for(auth, manager)

        assert (await http.get(f"/tenants/{other.id}", headers=_cookie(admin_t))).status_code == 200
        assert (await http.get(f"/tenants/{mine.id}", headers=_cookie(manager_t))).status_code == 200
        assert (await http.get(f"/tenants/{other.id}", headers=_cookie(manager_t))).status_code == 403
