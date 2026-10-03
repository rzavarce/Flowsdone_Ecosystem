"""Tests for MessagingWindowService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.services.messaging_window import MessagingWindowService
from api_gateway.tests.support.fakes import FakeConversationRepository, make_conversation

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
SESSION = "p1:whatsapp_360dialog:34699000111"


async def test_the_window_is_measured_from_the_contacts_latest_message_across_conversations():
    older = make_conversation(session_id=SESSION, status="closed", last_inbound_at=NOW - timedelta(days=3))
    latest = make_conversation(session_id=SESSION, last_inbound_at=NOW - timedelta(hours=2))
    other_contact = make_conversation(session_id="p1:whatsapp_360dialog:other", last_inbound_at=NOW)
    service = MessagingWindowService(conversations=FakeConversationRepository(older, latest, other_contact))

    decision = await service.decide(session_id=SESSION, channel_type="whatsapp_360dialog", now=NOW)

    assert decision.free_form_allowed
    assert decision.window_closes_at == NOW + timedelta(hours=22)


async def test_a_contact_who_never_wrote_needs_a_template_on_whatsapp():
    service = MessagingWindowService(conversations=FakeConversationRepository())

    decision = await service.decide(session_id=SESSION, channel_type="whatsapp_360dialog", now=NOW)

    assert decision.mode == "template_required"
