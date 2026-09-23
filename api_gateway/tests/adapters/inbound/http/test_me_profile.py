"""HTTP tests for the self-service profile endpoints: `PATCH /me/profile`
and `GET|PUT|DELETE /me/avatar`."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.me import router
from app.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.manage_profile import (
    RemoveAvatarUseCase,
    SetAvatarUseCase,
    UpdateOwnProfileUseCase,
)
from app.core.config import settings
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakeTenantRepo,
    FakeUserAvatarRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio

CSRF = {"X-Requested-With": "fd-console"}
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


async def _world(role="client"):
    tenant = make_tenant()
    user = make_user(role=role, tenant_ids=[tenant.id])
    users = FakeUserRepo()
    users.add(user)
    tenants = FakeTenantRepo([tenant])
    sessions = FakeAuthSessionRepo()
    avatars = FakeUserAvatarRepo(users)
    token = await sessions.create(user.id, ttl_seconds=3600)
    state = dict(
        tenant_repo=tenants,
        user_avatar_repo=avatars,
        get_current_user_use_case=GetCurrentUserUseCase(
            sessions=sessions, user_repo=users, tenant_repo=tenants, session_ttl_seconds=3600
        ),
        update_own_profile_use_case=UpdateOwnProfileUseCase(user_repo=users, tenant_repo=tenants),
        set_avatar_use_case=SetAvatarUseCase(avatar_repo=avatars),
        remove_avatar_use_case=RemoveAvatarUseCase(avatar_repo=avatars),
    )
    headers = {"Cookie": f"{settings.AUTH_COOKIE_NAME}={token}", **CSRF}
    return state, headers, users, user


async def test_any_role_edits_its_own_profile():
    state, headers, users, user = await _world(role="consultant")
    async with client_for_router(router, **state) as client:
        resp = await client.patch(
            "/me/profile",
            headers=headers,
            json={"name": "Carla C.", "phone": "+34 600 000 000", "social_links": {"linkedin": "https://linkedin.com/in/c"}},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Carla C."
    assert body["phone"] == "+34 600 000 000"
    assert body["social_links"] == {"linkedin": "https://linkedin.com/in/c"}
    assert body["role"] == "consultant"
    assert users.users[user.id].phone == "+34 600 000 000"


async def test_role_and_tenants_cannot_be_changed_through_the_profile():
    state, headers, users, user = await _world()
    async with client_for_router(router, **state) as client:
        resp = await client.patch("/me/profile", headers=headers, json={"role": "admin", "tenant_ids": []})
    assert resp.status_code == 200
    assert users.users[user.id].role == "client"
    assert users.users[user.id].tenant_ids == user.tenant_ids


async def test_invalid_profile_is_400_and_needs_session_and_csrf_header():
    state, headers, *_ = await _world()
    no_csrf = {k: v for k, v in headers.items() if k != "X-Requested-With"}
    async with client_for_router(router, **state) as client:
        bad = await client.patch("/me/profile", headers=headers, json={"social_links": {"website": "javascript:x"}})
        anon = await client.patch("/me/profile", headers=CSRF, json={"name": "X"})
        forged = await client.patch("/me/profile", headers=no_csrf, json={"name": "X"})
    assert bad.status_code == 400
    assert anon.status_code == 401
    assert forged.status_code == 403


async def test_avatar_upload_download_and_removal():
    state, headers, *_ = await _world()
    async with client_for_router(router, **state) as client:
        assert (await client.get("/me/avatar", headers=headers)).status_code == 404

        put = await client.put("/me/avatar", headers={**headers, "Content-Type": "image/png"}, content=PNG)
        assert put.status_code == 200
        assert put.json()["avatar_updated_at"] is not None

        got = await client.get("/me/avatar", headers=headers)
        assert got.status_code == 200
        assert got.content == PNG
        assert got.headers["content-type"] == "image/png"
        assert got.headers["x-content-type-options"] == "nosniff"

        removed = await client.delete("/me/avatar", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["avatar_updated_at"] is None
        assert (await client.get("/me/avatar", headers=headers)).status_code == 404


async def test_avatar_rejects_non_images_and_oversized_bodies():
    state, headers, *_ = await _world()
    async with client_for_router(router, **state) as client:
        svg = await client.put("/me/avatar", headers=headers, content=b"<svg onload=alert(1)/>")
        big = await client.put("/me/avatar", headers=headers, content=PNG + b"0" * (3 * 1024 * 1024))
    assert svg.status_code == 400
    assert big.status_code == 413
