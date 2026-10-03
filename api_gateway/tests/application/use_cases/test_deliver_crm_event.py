"""Tests for DeliverCrmEventUseCase (retries, dead letters, drops)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.application.use_cases.deliver_crm_event import DeliverCrmEventUseCase
from app.domain.models.crm import CrmEvent
from app.domain.ports.outbound import CrmDeliveryError
from api_gateway.tests.support.fakes import FakeCrmIntegrationRepository, make_crm_integration

pytestmark = pytest.mark.anyio


class ScriptedProvider:
    """Fails with the given exceptions, then succeeds."""

    def __init__(self, *failures):
        self.failures = list(failures)
        self.calls = 0

    async def deliver(self, event, integration):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)


class DeadLetters:
    def __init__(self):
        self.parked = []

    async def publish_dead(self, event, *, reason):
        self.parked.append((event, reason))


def _setup(provider, *, status="active", max_attempts=4):
    integration = make_crm_integration(status=status)
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    dead = DeadLetters()
    use_case = DeliverCrmEventUseCase(
        integrations=FakeCrmIntegrationRepository(integration),
        providers={"generic_webhook": provider},
        dead_letters=dead,
        max_attempts=max_attempts,
        backoff_seconds=2,
        sleep=sleep,
    )
    event = CrmEvent(
        id=uuid4(), type="handoff.started", integration_id=integration.id, handoff_id=uuid4(),
        conversation_id="c1", occurred_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
    )
    return use_case, event, waits, dead


async def test_transient_failures_are_retried_with_exponential_backoff():
    provider = ScriptedProvider(CrmDeliveryError("503"), CrmDeliveryError("timeout"))
    use_case, event, waits, dead = _setup(provider)

    assert await use_case.execute(event) == "delivered"
    assert provider.calls == 3 and waits == [2, 4] and dead.parked == []


async def test_running_out_of_attempts_parks_the_event():
    provider = ScriptedProvider(*[CrmDeliveryError("503")] * 4)
    use_case, event, waits, dead = _setup(provider, max_attempts=4)

    assert await use_case.execute(event) == "dead"
    assert provider.calls == 4 and waits == [2, 4, 8]
    assert dead.parked[0][0].id == event.id and "4 attempts" in dead.parked[0][1]


async def test_a_permanent_failure_is_parked_without_retrying():
    provider = ScriptedProvider(ValueError("400 bad payload"))
    use_case, event, waits, dead = _setup(provider)

    assert await use_case.execute(event) == "dead"
    assert provider.calls == 1 and waits == [] and "permanent" in dead.parked[0][1]


async def test_events_of_an_inactive_or_deleted_integration_are_dropped():
    provider = ScriptedProvider()
    use_case, event, _, dead = _setup(provider, status="inactive")

    assert await use_case.execute(event) == "dropped"
    assert provider.calls == 0 and dead.parked == []

    deleted = event.model_copy(update={"integration_id": uuid4()})
    assert await use_case.execute(deleted) == "dropped"


async def test_a_provider_without_adapter_is_parked():
    use_case, event, _, dead = _setup(ScriptedProvider())
    use_case._providers = {}

    assert await use_case.execute(event) == "dead"
    assert "no adapter" in dead.parked[0][1]
