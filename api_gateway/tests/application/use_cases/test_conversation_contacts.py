"""Tests for ManageConversationContactsUseCase: contact cards of conversations."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.conversation_contacts import (
    InvalidContactError,
    ManageConversationContactsUseCase,
    contact_key,
)
from api_gateway.tests.support.fakes import FakeContactRepo, FakeConversationRepository, make_conversation

pytestmark = pytest.mark.anyio


def _world(*conversations):
    contacts = FakeContactRepo()
    use_case = ManageConversationContactsUseCase(
        contacts=contacts, conversations=FakeConversationRepository(*conversations)
    )
    return use_case, contacts


async def test_staff_name_a_contact_and_every_conversation_with_them_shows_it():
    tenant = uuid4()
    first = make_conversation(tenant_id=tenant, channel_type="voice", contact="+34600111222")
    second = make_conversation(tenant_id=tenant, channel_type="voice", contact="+34600111222")
    other = make_conversation(tenant_id=tenant, channel_type="voice", contact="+34600999999")
    use_case, _ = _world(first, second, other)

    card = await use_case.update(first, {"name": "  Ana   Pérez ", "email": "Ana@Example.com"})

    assert card.name == "Ana Pérez" and card.email == "ana@example.com"
    cards = await use_case.for_conversations([first, second, other])
    assert cards[first.id].name == cards[second.id].name == "Ana Pérez"
    assert other.id not in cards


async def test_the_same_identifier_on_another_tenant_or_channel_is_another_contact():
    tenant = uuid4()
    voice = make_conversation(tenant_id=tenant, channel_type="voice", contact="+34600111222")
    whatsapp = make_conversation(tenant_id=tenant, channel_type="whatsapp_evolution", contact="+34600111222")
    other_tenant = make_conversation(tenant_id=uuid4(), channel_type="voice", contact="+34600111222")
    use_case, _ = _world(voice, whatsapp, other_tenant)

    await use_case.update(voice, {"name": "Ana"})

    cards = await use_case.for_conversations([voice, whatsapp, other_tenant])
    assert set(cards) == {voice.id}


async def test_staff_can_clear_a_field_and_untouched_fields_stay():
    conversation = make_conversation()
    use_case, contacts = _world(conversation)
    await use_case.update(conversation, {"name": "Ana", "phone": "600111222", "notes": "Cliente VIP"})

    card = await use_case.update(conversation, {"phone": ""})

    assert card.name == "Ana" and card.phone is None and card.notes == "Cliente VIP"


@pytest.mark.parametrize(
    "fields", [{"email": "ana(at)example"}, {"name": "x" * 121}, {"notes": "n" * 2001}, {"phone": "1" * 41}]
)
async def test_invalid_values_are_refused(fields):
    conversation = make_conversation()
    use_case, contacts = _world(conversation)

    with pytest.raises(InvalidContactError):
        await use_case.update(conversation, fields)
    assert contacts.contacts == {}


async def test_an_agent_fills_only_what_the_card_does_not_have():
    conversation = make_conversation(channel_type="voice", contact="client:demo-abc")
    use_case, contacts = _world(conversation)
    await use_case.update(conversation, {"name": "Ana Pérez"})

    card = await use_case.capture(conversation.id, {"name": "Ana Peres", "email": "ana@example.com", "phone": ""})

    assert card.name == "Ana Pérez"  # staff typed it: the (maybe misheard) one doesn't replace it
    assert card.email == "ana@example.com" and card.phone is None


async def test_an_agent_on_an_unknown_conversation_changes_nothing():
    use_case, contacts = _world()

    assert await use_case.capture(uuid4(), {"name": "Ana"}) is None
    assert contacts.contacts == {}


async def test_an_agent_with_nothing_to_say_returns_the_current_card():
    conversation = make_conversation()
    use_case, contacts = _world(conversation)

    assert await use_case.capture(conversation.id, {"name": "", "email": None}) is None
    await use_case.update(conversation, {"name": "Ana"})
    assert (await use_case.capture(conversation.id, {})).name == "Ana"
    assert contact_key(conversation) in contacts.contacts
