"""Tests for the shared register_or_compensate helper."""

from __future__ import annotations

import pytest

from api_gateway.app.application.services.webhook_registration import (
    WebhookRegistrationError,
    register_or_compensate,
)
from api_gateway.tests.support.fakes import FakeWebhookRegistrar

pytestmark = pytest.mark.anyio


async def test_success_never_triggers_compensation():
    registrar = FakeWebhookRegistrar()
    compensated = False

    async def on_failure():
        nonlocal compensated
        compensated = True

    await register_or_compensate(
        registrar=registrar,
        external_id="ext-1",
        credentials={"a": 1},
        channel_type="telegram",
        on_failure=on_failure,
    )

    assert compensated is False
    assert registrar.register_calls == [{"external_id": "ext-1", "credentials": {"a": 1}}]


async def test_failure_runs_compensation_then_raises_typed_error():
    registrar = FakeWebhookRegistrar(fail=True)
    compensated = False

    async def on_failure():
        nonlocal compensated
        compensated = True

    with pytest.raises(WebhookRegistrationError):
        await register_or_compensate(
            registrar=registrar,
            external_id="ext-1",
            credentials={},
            channel_type="telegram",
            on_failure=on_failure,
        )

    assert compensated is True


async def test_original_exception_is_chained():
    registrar = FakeWebhookRegistrar(fail=True)

    async def on_failure():
        return None

    with pytest.raises(WebhookRegistrationError) as exc_info:
        await register_or_compensate(
            registrar=registrar,
            external_id="ext-1",
            credentials={},
            channel_type="telegram",
            on_failure=on_failure,
        )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
