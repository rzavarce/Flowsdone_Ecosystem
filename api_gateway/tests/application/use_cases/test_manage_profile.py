"""Tests for the profile use cases: field validation, self-service edit and photos."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.manage_profile import (
    AVATAR_MAX_BYTES,
    InvalidAvatarError,
    RemoveAvatarUseCase,
    SetAvatarUseCase,
    UpdateOwnProfileUseCase,
    normalize_profile_fields,
    sniff_image_type,
)
from app.application.use_cases.manage_users import UpdateUserUseCase
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserAvatarRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 32


# ------------------------------------------------------- normalize_profile_fields


def test_unsent_fields_are_left_out():
    assert normalize_profile_fields() == {}


def test_trims_and_keeps_valid_values():
    fields = normalize_profile_fields(
        phone=" +34 (600) 12-34.56 ",
        address="  Calle Mayor 1, Madrid ",
        social_links={"linkedin": " https://linkedin.com/in/x ", "x": ""},
    )
    assert fields == {
        "phone": "+34 (600) 12-34.56",
        "address": "Calle Mayor 1, Madrid",
        "social_links": {"linkedin": "https://linkedin.com/in/x"},
    }


def test_empty_strings_mean_clear():
    assert normalize_profile_fields(phone="  ", address="") == {"phone": "", "address": ""}


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(phone="llámame"),
        dict(phone="12"),
        dict(address="x" * 301),
        dict(social_links={"myspace": "https://myspace.com/x"}),
        dict(social_links={"website": "javascript:alert(1)"}),
        dict(social_links={"website": "ftp://example.com"}),
        dict(social_links={"website": "https://"}),
    ],
)
def test_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        normalize_profile_fields(**kwargs)


@pytest.mark.parametrize(
    "data,expected",
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"), (b"<svg></svg>", None), (b"GIF89a", None)],
)
def test_sniffs_only_jpeg_png_and_webp(data, expected):
    assert sniff_image_type(data) == expected


# --------------------------------------------------------- UpdateOwnProfileUseCase


async def _own_profile_setup():
    tenant = make_tenant()
    user = make_user(role="client", tenant_ids=[tenant.id])
    users = FakeUserRepo()
    users.add(user)
    return UpdateOwnProfileUseCase(user_repo=users, tenant_repo=FakeTenantRepo([tenant])), users, user, tenant


async def test_user_updates_own_profile_and_gets_the_console_view_back():
    use_case, users, user, tenant = await _own_profile_setup()
    result = await use_case.execute(
        user.id, name=" Carla Nueva ", phone="600 123 456", social_links={"website": "https://carla.dev"}
    )
    assert result.name == "Carla Nueva"
    assert result.phone == "600 123 456"
    assert result.social_links == {"website": "https://carla.dev"}
    assert [t.id for t in result.tenants] == [tenant.id]
    # Role and tenants untouched.
    assert users.users[user.id].role == "client"


async def test_clearing_a_field_stores_none():
    use_case, users, user, _ = await _own_profile_setup()
    await use_case.execute(user.id, phone="600 123 456")
    await use_case.execute(user.id, phone="")
    assert users.users[user.id].phone is None


async def test_blank_name_is_rejected():
    use_case, _, user, _ = await _own_profile_setup()
    with pytest.raises(ValueError):
        await use_case.execute(user.id, name="   ")


async def test_unknown_user_returns_none():
    use_case, *_ = await _own_profile_setup()
    assert await use_case.execute(uuid4(), name="X") is None


# ------------------------------------------------------ UpdateUserUseCase (admin)


async def test_admin_update_accepts_profile_fields_without_closing_sessions():
    tenant = make_tenant()
    user = make_user(role="client", tenant_ids=[tenant.id])
    users, sessions = FakeUserRepo(), FakeAuthSessionRepo()
    users.add(user)
    token = await sessions.create(user.id, ttl_seconds=60)
    update = UpdateUserUseCase(
        user_repo=users, tenant_repo=FakeTenantRepo([tenant]), hasher=FakePasswordHasher(), sessions=sessions
    )
    updated = await update.execute(user.id, address="Av. Siempre Viva 742", social_links={"x": "https://x.com/c"})
    assert updated.address == "Av. Siempre Viva 742"
    assert updated.social_links == {"x": "https://x.com/c"}
    assert token in sessions.sessions


async def test_admin_update_rejects_invalid_profile_fields():
    user = make_user(role="admin")
    users = FakeUserRepo()
    users.add(user)
    update = UpdateUserUseCase(
        user_repo=users, tenant_repo=FakeTenantRepo([]), hasher=FakePasswordHasher(), sessions=FakeAuthSessionRepo()
    )
    with pytest.raises(ValueError):
        await update.execute(user.id, phone="no es un teléfono")


# ------------------------------------------------------------------ avatars


async def test_set_and_remove_avatar():
    user = make_user()
    users = FakeUserRepo()
    users.add(user)
    avatars = FakeUserAvatarRepo(users)

    updated = await SetAvatarUseCase(avatar_repo=avatars).execute(user.id, PNG)
    assert updated.avatar_updated_at is not None
    assert (await avatars.get(user.id)).content_type == "image/png"

    removed = await RemoveAvatarUseCase(avatar_repo=avatars).execute(user.id)
    assert removed.avatar_updated_at is None
    assert await avatars.get(user.id) is None


@pytest.mark.parametrize("data", [b"", b"<svg onload=alert(1)></svg>", JPEG + b"0" * AVATAR_MAX_BYTES])
async def test_invalid_avatars_are_rejected(data):
    user = make_user()
    users = FakeUserRepo()
    users.add(user)
    with pytest.raises(InvalidAvatarError):
        await SetAvatarUseCase(avatar_repo=FakeUserAvatarRepo(users)).execute(user.id, data)


async def test_avatar_for_unknown_user_returns_none():
    avatars = FakeUserAvatarRepo(FakeUserRepo())
    assert await SetAvatarUseCase(avatar_repo=avatars).execute(uuid4(), JPEG) is None
