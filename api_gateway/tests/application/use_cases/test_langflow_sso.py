"""Tests for the embedded-Langflow SSO use cases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.langflow_sso import (
    LangflowTargetNotFoundError,
    PrepareLangflowSessionUseCase,
    RedeemLangflowTicketUseCase,
)
from app.domain.models.langflow_account import LangflowAccount
from app.domain.models.project import Project
from app.domain.ports.outbound import AlreadyExistsError, LangflowSessionError, LangflowTokens
from api_gateway.tests.support.admin_world import InMemoryRepo
from api_gateway.tests.support.fakes import FakeSecretGenerator, FakeTenantRepo, make_tenant

pytestmark = pytest.mark.anyio


class FakeAccounts:
    def __init__(self) -> None:
        self.accounts: Dict[UUID, LangflowAccount] = {}
        self.folders: Dict[UUID, str] = {}
        self.race_winner: Optional[LangflowAccount] = None

    async def get(self, tenant_id):
        return self.accounts.get(tenant_id)

    async def create(self, *, tenant_id, username, password):
        if self.race_winner is not None:
            # Otra petición se adelantó: su fila ya está guardada.
            self.accounts[tenant_id] = self.race_winner
            raise AlreadyExistsError("duplicate")
        account = LangflowAccount(
            tenant_id=tenant_id, username=username, password=password, created_at=datetime.now(timezone.utc)
        )
        self.accounts[tenant_id] = account
        return account

    async def set_langflow_user_id(self, tenant_id, langflow_user_id):
        self.accounts[tenant_id] = self.accounts[tenant_id].model_copy(update={"langflow_user_id": langflow_user_id})

    async def get_folder(self, project_id):
        return self.folders.get(project_id)

    async def save_folder(self, project_id, folder_id):
        self.folders[project_id] = folder_id


class FakeLangflow:
    def __init__(self) -> None:
        self.users: Dict[str, str] = {}
        self.folders: Dict[str, str] = {}
        self.calls: List[str] = []
        self.fail_login = False
        self._created = 0

    async def ensure_user(self, username, password):
        self.calls.append("ensure_user")
        self.users[username] = password
        return f"lf-{username}"

    async def login(self, username, password):
        self.calls.append("login")
        if self.fail_login or self.users.get(username) != password:
            raise LangflowSessionError("login refused")
        return LangflowTokens(access_token=f"access-{username}", refresh_token=f"refresh-{username}")

    async def list_projects(self, access_token):
        self.calls.append("list_projects")
        return dict(self.folders)

    async def create_project(self, access_token, name):
        self.calls.append("create_project")
        self._created += 1
        folder_id = f"folder-{self._created}"
        self.folders[folder_id] = name
        return folder_id

    async def delete_project(self, access_token, folder_id):
        self.calls.append("delete_project")
        self.folders.pop(folder_id, None)


class FakeTickets:
    def __init__(self) -> None:
        self.issued: Dict[str, dict] = {}
        self.ttl: Optional[int] = None

    async def issue(self, payload, *, ttl_seconds):
        self.ttl = ttl_seconds
        ticket = f"ticket-{len(self.issued) + 1}"
        self.issued[ticket] = payload
        return ticket

    async def redeem(self, ticket):
        return self.issued.pop(ticket, None)


class World:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.tenant = make_tenant(slug="acme", name="Acme")
        self.tenants = FakeTenantRepo([self.tenant])
        self.projects = InMemoryRepo(
            lambda **f: Project(id=uuid4(), status="active", created_at=now, updated_at=now, **f), "tenant_id"
        )
        self.accounts = FakeAccounts()
        self.langflow = FakeLangflow()
        self.tickets = FakeTickets()
        self.prepare = PrepareLangflowSessionUseCase(
            tenant_repo=self.tenants,
            project_repo=self.projects,
            accounts=self.accounts,
            langflow=self.langflow,
            secret_generator=FakeSecretGenerator(),
            tickets=self.tickets,
            ticket_ttl_seconds=30,
        )
        self.redeem = RedeemLangflowTicketUseCase(
            accounts=self.accounts, langflow=self.langflow, tickets=self.tickets
        )

    async def add_project(self, name: str, tenant=None) -> Project:
        return await self.projects.create(tenant_id=(tenant or self.tenant).id, name=name, slug=name.lower())


async def test_first_open_creates_the_tenant_user_and_a_folder_per_project():
    w = World()
    p1, p2 = await w.add_project("Ventas"), await w.add_project("Soporte")

    ticket = await w.prepare.execute(w.tenant.id)

    account = w.accounts.accounts[w.tenant.id]
    assert account.username == "tenant-acme"
    assert account.langflow_user_id == "lf-tenant-acme"
    assert sorted(w.langflow.folders.values()) == ["Soporte", "Ventas"]
    assert set(w.accounts.folders) == {p1.id, p2.id}
    assert w.tickets.ttl == 30
    assert ticket in w.tickets.issued


async def test_lands_on_the_first_project_by_name_when_none_is_given():
    w = World()
    await w.add_project("Ventas")
    soporte = await w.add_project("Soporte")

    ticket = await w.prepare.execute(w.tenant.id)

    assert w.tickets.issued[ticket]["path"] == f"/all/folder/{w.accounts.folders[soporte.id]}"


async def test_lands_on_the_requested_project():
    w = World()
    ventas = await w.add_project("Ventas")
    await w.add_project("Soporte")

    ticket = await w.prepare.execute(w.tenant.id, ventas.id)

    assert w.tickets.issued[ticket]["path"] == f"/all/folder/{w.accounts.folders[ventas.id]}"


async def test_a_tenant_without_projects_lands_on_the_langflow_home():
    w = World()

    ticket = await w.prepare.execute(w.tenant.id)

    assert w.tickets.issued[ticket]["path"] == "/all"
    assert "list_projects" not in w.langflow.calls


async def test_second_open_reuses_everything():
    w = World()
    await w.add_project("Ventas")
    await w.prepare.execute(w.tenant.id)
    w.langflow.calls.clear()

    await w.prepare.execute(w.tenant.id)

    assert "ensure_user" not in w.langflow.calls
    assert "create_project" not in w.langflow.calls


async def test_a_folder_deleted_in_langflow_is_recreated():
    w = World()
    ventas = await w.add_project("Ventas")
    await w.prepare.execute(w.tenant.id)
    old = w.accounts.folders[ventas.id]
    w.langflow.folders.clear()

    await w.prepare.execute(w.tenant.id)

    assert w.accounts.folders[ventas.id] != old
    assert w.accounts.folders[ventas.id] in w.langflow.folders


async def test_a_failure_after_storing_the_account_is_retried_with_the_same_password():
    w = World()
    real = w.langflow.ensure_user

    async def flaky(username, password):
        raise LangflowSessionError("boom")

    w.langflow.ensure_user = flaky
    with pytest.raises(LangflowSessionError):
        await w.prepare.execute(w.tenant.id)
    stored = w.accounts.accounts[w.tenant.id]
    assert stored.langflow_user_id is None

    w.langflow.ensure_user = real
    await w.prepare.execute(w.tenant.id)

    assert w.langflow.users["tenant-acme"] == stored.password.get_secret_value()
    assert w.accounts.accounts[w.tenant.id].password == stored.password


async def test_losing_a_creation_race_uses_the_winners_password():
    w = World()
    w.accounts.race_winner = LangflowAccount(
        tenant_id=w.tenant.id, username="tenant-acme", password="winner-pass", created_at=datetime.now(timezone.utc)
    )

    await w.prepare.execute(w.tenant.id)

    assert w.langflow.users["tenant-acme"] == "winner-pass"


async def test_unknown_tenant_or_foreign_project_is_not_found():
    w = World()
    other = make_tenant(slug="other")
    foreign = await w.add_project("Ajeno", tenant=other)
    with pytest.raises(LangflowTargetNotFoundError):
        await w.prepare.execute(uuid4())
    with pytest.raises(LangflowTargetNotFoundError):
        await w.prepare.execute(w.tenant.id, foreign.id)
    assert w.accounts.accounts == {}


async def test_redeem_logs_in_as_the_tenant_user_and_returns_the_landing_path():
    w = World()
    await w.add_project("Ventas")
    ticket = await w.prepare.execute(w.tenant.id)

    landing = await w.redeem.execute(ticket)

    assert landing.tokens.access_token == "access-tenant-acme"
    assert landing.path.startswith("/all/folder/")


async def test_a_ticket_only_works_once():
    w = World()
    ticket = await w.prepare.execute(w.tenant.id)
    assert await w.redeem.execute(ticket) is not None
    assert await w.redeem.execute(ticket) is None


async def test_unknown_tickets_are_rejected():
    assert await World().redeem.execute("nope") is None


async def test_redeem_never_redirects_outside_the_langflow_app():
    w = World()
    await w.prepare.execute(w.tenant.id)
    w.tickets.issued["evil"] = {"tenant_id": str(w.tenant.id), "path": "//evil.example/x"}

    landing = await w.redeem.execute("evil")

    assert landing.path == "/all"


async def test_redeem_surfaces_a_langflow_login_failure():
    w = World()
    ticket = await w.prepare.execute(w.tenant.id)
    w.langflow.fail_login = True
    with pytest.raises(LangflowSessionError):
        await w.redeem.execute(ticket)
