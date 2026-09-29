"""Tests for ManageConversationContactsUseCase: contact cards of conversations."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.conversation_contacts import (
    InvalidContactError,
    ManageConversationContactsUseCase,
    contact_key,
)
from app.domain.models.conversation_contact import SenderProfile
from api_gateway.tests.support.fakes import FakeContactRepo, make_conversation

pytestmark = pytest.mark.anyio


def _world(*conversations):
    contacts = FakeContactRepo()
    return ManageConversationContactsUseCase(contacts=contacts), contacts


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


async def test_the_channel_starts_the_card_and_the_chat_completes_it():
    conversation = make_conversation(channel_type="whatsapp_evolution", contact="34600111222@s.whatsapp.net")
    use_case, _ = _world(conversation)
    key = contact_key(conversation)

    card = await use_case.record_from_channel(
        key, profile=SenderProfile(name="Ana", phone="+34600111222"), text="Hola"
    )
    assert (card.name, card.phone, card.email) == ("Ana", "+34600111222", None)

    card = await use_case.record_from_channel(key, text="Mi correo es Ana@Example.com")
    assert card.email == "ana@example.com" and card.name == "Ana"


async def test_what_staff_typed_is_never_replaced_by_the_channel_or_the_chat():
    conversation = make_conversation(channel_type="telegram", contact="12345")
    use_case, _ = _world(conversation)
    await use_case.update(conversation, {"name": "Ana Pérez (clienta VIP)"})

    card = await use_case.record_from_channel(
        contact_key(conversation), profile=SenderProfile(name="ana", username="@ana"),
        text="Ana Peres", asked="¿Cómo te llamas?",
    )

    assert card.name == "Ana Pérez (clienta VIP)" and card.username == "@ana"


async def test_a_name_or_phone_is_taken_only_when_the_agent_asked_for_it():
    conversation = make_conversation(channel_type="webchat", contact="visitor-1")
    use_case, contacts = _world(conversation)
    key = contact_key(conversation)

    assert await use_case.record_from_channel(key, text="Roger", asked="¿En qué te ayudo?") is None
    assert await use_case.record_from_channel(key, text="mi pedido es 600112233") is None
    card = await use_case.record_from_channel(
        key, text="Roger Zavarce, 600 11 22 33", asked="Para la cita necesito tu nombre y teléfono"
    )

    assert (card.name, card.phone) == ("Roger Zavarce", "600112233")


async def test_nothing_to_record_does_not_touch_the_store():
    conversation = make_conversation()
    use_case, contacts = _world(conversation)

    assert await use_case.record_from_channel(contact_key(conversation), profile=SenderProfile(), text="hola") is None
    assert contacts.contacts == {}


async def test_an_out_of_bounds_channel_value_is_dropped_and_the_rest_kept():
    conversation = make_conversation()
    use_case, _ = _world(conversation)

    card = await use_case.record_from_channel(
        contact_key(conversation), profile=SenderProfile(name="x" * 500, phone="+34600111222")
    )

    assert card.name is None and card.phone == "+34600111222"
