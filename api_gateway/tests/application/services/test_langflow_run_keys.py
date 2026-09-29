"""Tests for LangflowRunKeys: each flow runs with its owner tenant's key."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from app.application.services.langflow_run_keys import RUN_KEY_NAME, LangflowRunKeys
from app.domain.models.langflow_account import LangflowAccount
from app.domain.ports.outbound import LangflowSessionError, LangflowTokens

pytestmark = pytest.mark.anyio

TENANT = uuid4()


class FakeAdmin:
    """Langflow: who owns each flow, logins and key creation."""

    def __init__(self, owners: Dict[str, Optional[str]], fail_owner: bool = False) -> None:
        self.owners = owners
        self.fail_owner = fail_owner
        self.owner_calls: List[str] = []
        self.logins: List[tuple] = []
        self.created: List[tuple] = []

    async def flow_owner(self, flow_id: str) -> Optional[str]:
        self.owner_calls.append(flow_id)
        if self.fail_owner:
            raise LangflowSessionError("langflow unreachable")
        return self.owners.get(flow_id)

    async def login(self, username: str, password: str) -> LangflowTokens:
        self.logins.append((username, password))
        return LangflowTokens(access_token=f"token-{username}", refresh_token="r")

    async def create_api_key(self, access_token: str, name: str) -> str:
        self.created.append((access_token, name))
        return f"sk-new-{len(self.created)}"


class FakeAccounts:
    """Tenant accounts keyed by their Langflow user id."""

    def __init__(self, accounts: List[LangflowAccount]) -> None:
        self.accounts = {a.langflow_user_id: a for a in accounts}
        self.stored_keys: Dict[UUID, str] = {}

    async def get_by_langflow_user_id(self, langflow_user_id: str) -> Optional[LangflowAccount]:
        return self.accounts.get(langflow_user_id)

    async def set_run_api_key(self, tenant_id: UUID, api_key: str) -> None:
        self.stored_keys[tenant_id] = api_key


def _account(run_api_key: Optional[str] = None) -> LangflowAccount:
    return LangflowAccount(
        tenant_id=TENANT,
        username="tenant-flowsdone",
        password="pw",
        langflow_user_id="u-tenant",
        run_api_key=run_api_key,
        created_at=datetime.now(timezone.utc),
    )


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_a_tenant_flow_uses_the_stored_key_without_logging_in():
    admin = FakeAdmin({"flow-1": "u-tenant"})
    keys = LangflowRunKeys(admin=admin, accounts=FakeAccounts([_account("sk-stored")]))

    assert await keys.key_for("flow-1") == "sk-stored"
    assert admin.logins == [] and admin.created == []


async def test_the_key_is_created_on_first_use_and_stored():
    admin = FakeAdmin({"flow-1": "u-tenant"})
    accounts = FakeAccounts([_account()])
    keys = LangflowRunKeys(admin=admin, accounts=accounts)

    key = await keys.key_for("flow-1")

    assert key == "sk-new-1"
    assert admin.logins == [("tenant-flowsdone", "pw")]
    assert admin.created == [("token-tenant-flowsdone", RUN_KEY_NAME)]
    assert accounts.stored_keys == {TENANT: "sk-new-1"}


async def test_owner_and_key_are_cached_between_messages():
    admin = FakeAdmin({"flow-1": "u-tenant"})
    keys = LangflowRunKeys(admin=admin, accounts=FakeAccounts([_account()]))

    first = await keys.key_for("flow-1")
    second = await keys.key_for("flow-1")

    assert first == second
    assert admin.owner_calls == ["flow-1"]
    assert len(admin.created) == 1


async def test_the_owner_is_asked_again_after_the_cache_expires():
    admin = FakeAdmin({"flow-1": "u-tenant"})
    clock = Clock()
    keys = LangflowRunKeys(admin=admin, accounts=FakeAccounts([_account("sk-stored")]), clock=clock)

    await keys.key_for("flow-1")
    clock.now += 601
    await keys.key_for("flow-1")

    assert admin.owner_calls == ["flow-1", "flow-1"]


async def test_a_flow_not_owned_by_a_tenant_uses_the_platform_key():
    keys = LangflowRunKeys(admin=FakeAdmin({"flow-1": "u-superuser"}), accounts=FakeAccounts([_account()]))

    assert await keys.key_for("flow-1") is None


async def test_an_unknown_flow_uses_the_platform_key():
    keys = LangflowRunKeys(admin=FakeAdmin({}), accounts=FakeAccounts([_account()]))

    assert await keys.key_for("missing") is None


async def test_a_failed_lookup_falls_back_to_the_platform_key():
    keys = LangflowRunKeys(admin=FakeAdmin({}, fail_owner=True), accounts=FakeAccounts([_account()]))

    assert await keys.key_for("flow-1") is None


async def test_replace_key_creates_a_new_one_and_caches_it():
    admin = FakeAdmin({"flow-1": "u-tenant"})
    accounts = FakeAccounts([_account("sk-deleted")])
    keys = LangflowRunKeys(admin=admin, accounts=accounts)
    assert await keys.key_for("flow-1") == "sk-deleted"

    new_key = await keys.replace_key("flow-1")

    assert new_key == "sk-new-1"
    assert accounts.stored_keys == {TENANT: "sk-new-1"}
    assert await keys.key_for("flow-1") == "sk-new-1"


async def test_replace_key_for_a_flow_never_resolved_does_nothing():
    admin = FakeAdmin({"flow-1": "u-tenant"})
    keys = LangflowRunKeys(admin=admin, accounts=FakeAccounts([_account()]))

    assert await keys.replace_key("flow-1") is None
    assert admin.created == []
