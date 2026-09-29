"""Tests for the contact cards the Switchboard starts and completes with
each inbound turn: the channel's profile on the first message, and the
details the contact gives in the chat."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.application.services.switchboard import Switchboard, build_conversation_id
from app.application.use_cases.conversation_contacts import ManageConversationContactsUseCase
from app.domain.models.conversation_contact import SenderProfile
from api_gateway.tests.support.fakes import (
    FakeAppConnector,
    FakeChannelConnectionRepo,
    FakeContactRepo,
    FakeOutboundHandler,
    FakeSessionHistoryRepository,
    FakeSessionRepository,
    make_channel_resolution,
)

pytestmark = pytest.mark.anyio


class FakeProfileLookup:
    """Records lookups and answers with a fixed profile."""

    def __init__(self, profile=None):
        self.profile = profile
        self.calls = []

    async def lookup(self, *, channel_type, sender_id, credentials):
        self.calls.append((channel_type, sender_id, credentials))
        return self.profile


class World:
    def __init__(self, channel_type="facebook", lookup=None, contacts=None):
        self.resolution = make_channel_resolution(
            channel_type=channel_type, external_id="ext-1", credentials={"page_access_token": "T"}
        )
        self.sessions = FakeSessionRepository()
        self.contacts = contacts or FakeContactRepo()
        self.lookup = lookup or FakeProfileLookup()
        self.connector = FakeAppConnector()
        self.switchboard = Switchboard(
            channel_connection_repo=FakeChannelConnectionRepo(resolution=self.resolution),
            session_repo=self.sessions,
            session_history_repo=FakeSessionHistoryRepository(),
            app_connectors={"langflow": self.connector},
            outbound_handler=FakeOutboundHandler(),
            session_ttl_seconds=3600,
            contacts=ManageConversationContactsUseCase(contacts=self.contacts),
            profile_lookup=self.lookup,
        )
        self.channel_type = channel_type

    async def says(self, text, profile=None, sender="user-7"):
        await self.switchboard.handle_inbound_turn(
            channel_type=self.channel_type,
            external_id="ext-1",
            external_conversation_key=sender,
            sender_id=sender,
            message_text=text,
            raw_payload={},
            sender_profile=profile,
        )

    def agent_says(self, text, sender="user-7"):
        session = self.sessions.sessions[build_conversation_id(self.resolution.project_id, self.channel_type, sender)]
        session.record_message(direction="outbound", text=text, app="langflow", timestamp=datetime.now(timezone.utc))

    def card(self, sender="user-7"):
        return self.contacts.contacts.get((self.resolution.tenant_id, self.channel_type, sender))


async def test_the_first_message_starts_the_card_with_what_the_channel_says():
    world = World(channel_type="whatsapp_evolution")

    await world.says("Hola", profile=SenderProfile(name="Ana", phone="+34600111222"))

    card = world.card()
    assert (card.name, card.phone) == ("Ana", "+34600111222")


async def test_a_facebook_sender_is_looked_up_once_per_session():
    world = World(channel_type="facebook", lookup=FakeProfileLookup(SenderProfile(name="Ana Pérez")))

    await world.says("Hola")
    await world.says("¿Tenéis cita el lunes?")

    assert world.card().name == "Ana Pérez"
    assert world.lookup.calls == [("facebook", "user-7", {"page_access_token": "T"})]


async def test_details_the_contact_gives_in_the_chat_are_added():
    world = World(channel_type="webchat")
    await world.says("Hola", profile=SenderProfile(name="client:webchat-1a2b3c4d"))
    world.agent_says("Claro, ¿me das tu teléfono y tu email?")

    await world.says("600 11 22 33, ana@example.com")

    card = world.card()
    assert (card.name, card.phone, card.email) == ("client:webchat-1a2b3c4d", "600112233", "ana@example.com")


async def test_a_name_the_agent_asked_for_is_saved():
    world = World(channel_type="voice")
    await world.says("Hola, quiero una cita", profile=SenderProfile(phone="+34600111222"))
    world.agent_says("Perfecto. ¿Cuál es tu nombre?")

    await world.says("Ana Pérez")

    assert world.card().name == "Ana Pérez"


async def test_a_contact_store_failure_never_stops_the_reply():
    class BrokenContacts(FakeContactRepo):
        async def upsert(self, *args, **kwargs):
            raise RuntimeError("db down")

    world = World(channel_type="whatsapp_evolution", contacts=BrokenContacts())

    await world.says("Hola", profile=SenderProfile(name="Ana"))

    assert len(world.connector.calls) == 1
