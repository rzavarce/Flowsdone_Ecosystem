"""Tests for DeleteChannelConnectionUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api_gateway.app.application.use_cases.delete_channel_connection import (
    DeleteChannelConnectionUseCase,
)
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakeWebhookRegistrar,
    make_channel_connection,
)

pytestmark = pytest.mark.anyio


async def test_unknown_connection_returns_false():
    repo = FakeChannelConnectionRepo(connection=None)
    use_case = DeleteChannelConnectionUseCase(repo, {"telegram": FakeWebhookRegistrar()})

    assert await use_case.execute(uuid4()) is False


async def test_deletes_and_deregisters_registrar_channel():
    connection = make_channel_connection(channel_type="telegram", credentials={"s": "x"})
    repo = FakeChannelConnectionRepo(connection=connection)
    registrar = FakeWebhookRegistrar()
    use_case = DeleteChannelConnectionUseCase(repo, {"telegram": registrar})

    deleted = await use_case.execute(connection.id)

    assert deleted is True
    assert repo.connection is None
    assert registrar.deregister_calls == [
        {"external_id": connection.external_id, "credentials": {"s": "x"}}
    ]


async def test_deregister_failure_does_not_block_deletion():
    connection = make_channel_connection(channel_type="telegram")
    repo = FakeChannelConnectionRepo(connection=connection)
    registrar = FakeWebhookRegistrar(fail=True)
    use_case = DeleteChannelConnectionUseCase(repo, {"telegram": registrar})

    deleted = await use_case.execute(connection.id)

    assert deleted is True
    assert repo.connection is None
    assert len(registrar.deregister_calls) == 1


async def test_channel_without_registrar_deletes_directly():
    connection = make_channel_connection(channel_type="whatsapp_evolution")
    repo = FakeChannelConnectionRepo(connection=connection)
    use_case = DeleteChannelConnectionUseCase(repo, {"telegram": FakeWebhookRegistrar()})

    deleted = await use_case.execute(connection.id)

    assert deleted is True
    assert repo.connection is None
