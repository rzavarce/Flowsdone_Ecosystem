"""CRM handoff, end to end at the application layer: a real Switchboard
with the "crm" connector, in-memory repositories and event queue.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.adapters.outbound.apps.crm_app_connector import CrmAppConnector
from app.application.services.crm_handoffs import CrmHandoffs
from app.application.services.messaging_window import MessagingWindowService
from app.application.services.switchboard import Switchboard, build_conversation_id
from app.application.use_cases.crm_handoff import (
    CloseHandoffUseCase,
    HandoffNotOpenError,
    HandoffNotPossibleError,
    OutsideMessagingWindowError,
    ReplyFromCrmUseCase,
    StartHandoffUseCase,
)
from app.domain.models.session import SessionMessage
from api_gateway.tests.support.fakes import (
    FakeAppConnector,
    FakeChannelConnectionRepo,
    FakeConversationRepository,
    FakeCrmEventPublisher,
    FakeCrmIntegrationRepository,
    FakeHandoffRepository,
    FakeOutboundHandler,
    FakeSessionHistoryRepository,
    FakeSessionRepository,
    make_channel_resolution,
    make_conversation,
    make_crm_integration,
    make_session,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


class World:
    """Everything a handoff touches, wired like main.py does."""

    def __init__(self, *, with_integration=True, last_inbound=NOW - timedelta(hours=1)):
        project_id = uuid4()
        self.session = make_session(
            id=build_conversation_id(project_id, "whatsapp_360dialog", "34699000111"),
            project_id=project_id,
            channel_type="whatsapp_360dialog",
            external_conversation_key="34699000111",
            last_messages=[
                SessionMessage(direction="inbound", text="Quiero hablar con una persona", app="langflow", timestamp=NOW),
            ],
        )
        self.integration = make_crm_integration(project_id=self.session.project_id)
        self.integrations = FakeCrmIntegrationRepository(*([self.integration] if with_integration else []))
        self.handoffs = FakeHandoffRepository()
        self.queue = FakeCrmEventPublisher()
        self.crm = CrmHandoffs(handoffs=self.handoffs, publisher=self.queue, clock=lambda: NOW)
        self.sessions = FakeSessionRepository(self.session)
        self.outbound = FakeOutboundHandler()
        self.bot = FakeAppConnector()
        resolution = make_channel_resolution(
            channel_type="whatsapp_360dialog", tenant_id=self.session.tenant_id, project_id=self.session.project_id
        )
        self.switchboard = Switchboard(
            channel_connection_repo=FakeChannelConnectionRepo(resolution=resolution),
            session_repo=self.sessions,
            session_history_repo=FakeSessionHistoryRepository(),
            app_connectors={"langflow": self.bot, "crm": CrmAppConnector(self.crm)},
            outbound_handler=self.outbound,
            session_ttl_seconds=86400,
            crm_handoffs=self.crm,
        )
        conversations = FakeConversationRepository(
            make_conversation(session_id=self.session.id, last_inbound_at=last_inbound)
        )
        self.start = StartHandoffUseCase(
            sessions=self.sessions, integrations=self.integrations, handoffs=self.handoffs,
            crm=self.crm, switchboard=self.switchboard, clock=lambda: NOW,
        )
        self.reply = ReplyFromCrmUseCase(
            sessions=self.sessions, handoffs=self.handoffs, crm=self.crm,
            window=MessagingWindowService(conversations=conversations), outbound=self.outbound, clock=lambda: NOW,
        )
        self.close = CloseHandoffUseCase(handoffs=self.handoffs, switchboard=self.switchboard, clock=lambda: NOW)

    async def contact_writes(self, text):
        await self.switchboard.handle_inbound_turn(
            channel_type="whatsapp_360dialog", external_id="34600111222",
            external_conversation_key="34699000111", sender_id="34699000111",
            message_text=text, raw_payload={},
        )


async def test_starting_a_handoff_silences_the_bot_and_sends_the_conversation_to_the_crm():
    w = World()

    handoff = await w.start.execute(session_id=w.session.id, reason="pide un humano")

    assert (await w.sessions.get(w.session.id)).current_app == "crm"
    assert handoff.status == "open" and handoff.integration_id == w.integration.id
    (event,) = w.queue.events
    assert event.type == "handoff.started"
    assert event.conversation_id == w.session.id
    assert event.data["reason"] == "pide un humano"
    assert event.data["contact"]["id"] == "34699000111"
    assert event.data["transcript"][0]["text"] == "Quiero hablar con una persona"


async def test_starting_twice_returns_the_open_handoff_without_new_events():
    w = World()
    first = await w.start.execute(session_id=w.session.id)

    again = await w.start.execute(session_id=w.session.id)

    assert again.id == first.id and len(w.queue.events) == 1


@pytest.mark.parametrize("problem", ["no_session", "no_integration", "inactive_integration"])
async def test_a_handoff_needs_a_conversation_and_an_active_integration(problem):
    w = World(with_integration=problem != "no_integration")
    if problem == "inactive_integration":
        await w.integrations.update(w.integration.id, status="inactive")
    session_id = "missing" if problem == "no_session" else w.session.id

    with pytest.raises(HandoffNotPossibleError):
        await w.start.execute(session_id=session_id)

    assert w.queue.events == [] and (await w.sessions.get(w.session.id)).current_app == "langflow"


async def test_while_handed_over_the_contacts_messages_go_to_the_crm_not_to_the_bot():
    w = World()
    await w.start.execute(session_id=w.session.id)

    await w.contact_writes("¿Hay alguien?")

    assert w.bot.calls == []
    assert w.queue.events[-1].type == "message.inbound"
    assert w.queue.events[-1].data["text"] == "¿Hay alguien?"


async def test_the_agents_reply_is_delivered_on_the_contacts_channel():
    w = World()
    await w.start.execute(session_id=w.session.id)

    await w.reply.execute(integration_id=w.integration.id, conversation_id=w.session.id, text="Hola, soy Marta")

    (envelope,) = w.outbound.delivered
    assert envelope.payload == {"message": "Hola, soy Marta"}
    assert envelope.channel == "whatsapp_360dialog"
    assert envelope.meta.conversation_id == w.session.id
    assert envelope.meta.external_conversation_key == "34699000111"


async def test_a_reply_outside_the_24h_window_is_refused():
    w = World(last_inbound=NOW - timedelta(hours=30))
    await w.start.execute(session_id=w.session.id)

    with pytest.raises(OutsideMessagingWindowError) as caught:
        await w.reply.execute(integration_id=w.integration.id, conversation_id=w.session.id, text="¿Sigues ahí?")

    assert caught.value.decision.mode == "template_required"
    assert w.outbound.delivered == []


async def test_another_integration_cannot_reply_or_close():
    w = World()
    await w.start.execute(session_id=w.session.id)
    other = make_crm_integration().id

    with pytest.raises(HandoffNotOpenError):
        await w.reply.execute(integration_id=other, conversation_id=w.session.id, text="x")
    with pytest.raises(HandoffNotOpenError):
        await w.close.execute(integration_id=other, conversation_id=w.session.id)


async def test_closing_the_ticket_gives_the_conversation_back_to_the_bot():
    w = World()
    await w.start.execute(session_id=w.session.id)

    closed = await w.close.execute(integration_id=w.integration.id, conversation_id=w.session.id)
    await w.contact_writes("Gracias")

    assert (closed.status, closed.close_reason) == ("closed", "agent")
    assert (await w.sessions.get(w.session.id)).current_app == "langflow"
    assert len(w.bot.calls) == 1
    with pytest.raises(HandoffNotOpenError):
        await w.reply.execute(integration_id=w.integration.id, conversation_id=w.session.id, text="x")


async def test_when_the_session_expires_the_next_message_goes_to_the_bot_and_the_crm_is_told():
    w = World()
    handoff = await w.start.execute(session_id=w.session.id)
    await w.sessions.delete(w.session.id)  # Redis TTL ran out

    await w.contact_writes("Hola de nuevo")

    assert len(w.bot.calls) == 1
    assert w.handoffs.handoffs[handoff.id].status == "expired"
    assert w.queue.events[-1].type == "handoff.expired"


async def test_a_reply_after_the_session_expired_expires_the_handoff_and_is_refused():
    w = World()
    handoff = await w.start.execute(session_id=w.session.id)
    await w.sessions.delete(w.session.id)

    with pytest.raises(HandoffNotOpenError):
        await w.reply.execute(integration_id=w.integration.id, conversation_id=w.session.id, text="x")

    assert w.handoffs.handoffs[handoff.id].status == "expired"
    assert w.queue.events[-1].type == "handoff.expired"


async def test_without_a_queue_events_are_logged_instead_of_lost_silently(caplog):
    w = World()
    w.crm._publisher = None

    await w.start.execute(session_id=w.session.id)

    assert any(r.getMessage() == "crm.event.no_queue" for r in caplog.records)
