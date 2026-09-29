"""Integration tests for SqlAlchemyLangflowAccountRepository's run key
support against a real, migrated, throwaway Postgres (TEST_POSTGRES_URL)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

from app.adapters.outbound.db.langflow_account_repository import SqlAlchemyLangflowAccountRepository
from app.infrastructure.database import create_sessionmaker

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]


@pytest.fixture
async def ctx():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    tenant_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug, status) VALUES (:id, 'it', :slug, 'active')"),
            {"id": tenant_id, "slug": f"it-{tenant_id}"},
        )
    yield dict(engine=engine, sessionmaker=create_sessionmaker(engine), tenant_id=tenant_id)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
    await engine.dispose()


async def test_run_key_is_stored_encrypted_next_to_the_password(ctx):
    repo = SqlAlchemyLangflowAccountRepository(ctx["sessionmaker"])
    tenant_id = ctx["tenant_id"]
    langflow_user_id = f"u-{uuid.uuid4()}"
    await repo.create(tenant_id=tenant_id, username=f"it-{tenant_id}", password="pw-secret")
    await repo.set_langflow_user_id(tenant_id, langflow_user_id)

    assert (await repo.get(tenant_id)).run_api_key is None

    await repo.set_run_api_key(tenant_id, "sk-tenant-key")

    account = await repo.get(tenant_id)
    assert account.run_api_key.get_secret_value() == "sk-tenant-key"
    assert account.password.get_secret_value() == "pw-secret"
    async with ctx["engine"].connect() as conn:
        raw = (
            await conn.execute(text("SELECT credentials::text FROM langflow_accounts WHERE tenant_id = :id"), {"id": tenant_id})
        ).scalar_one()
    assert "sk-tenant-key" not in raw and "pw-secret" not in raw


async def test_accounts_are_found_by_their_langflow_user(ctx):
    repo = SqlAlchemyLangflowAccountRepository(ctx["sessionmaker"])
    tenant_id = ctx["tenant_id"]
    langflow_user_id = f"u-{uuid.uuid4()}"
    await repo.create(tenant_id=tenant_id, username=f"it-{tenant_id}", password="pw")
    await repo.set_langflow_user_id(tenant_id, langflow_user_id)

    found = await repo.get_by_langflow_user_id(langflow_user_id)

    assert found.tenant_id == tenant_id
    assert await repo.get_by_langflow_user_id("u-nobody") is None


async def test_setting_a_run_key_for_an_unknown_tenant_is_a_noop(ctx):
    repo = SqlAlchemyLangflowAccountRepository(ctx["sessionmaker"])

    await repo.set_run_api_key(uuid.uuid4(), "sk-x")
