"""Tests for the usage metering functions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.usage_metering import (
    infer_llm_provider,
    usage_event_id,
    usage_from_generation,
    usage_from_message,
)
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.ports.outbound import LlmGeneration
from api_gateway.tests.support.fakes import make_conversation

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _message(**overrides) -> ConversationMessageRecorded:
    defaults = dict(
        message_id=uuid4(), timestamp=T0, tenant_id=uuid4(), project_id=uuid4(), agent_id=uuid4(),
        conversation_id=uuid4(), session_id="s", channel_type="whatsapp_evolution",
        channel_connection_id=uuid4(), direction="inbound", sender_type="contact", app="langflow",
        contact="34600", text="hola",
    )
    defaults.update(overrides)
    return ConversationMessageRecorded(**defaults)


def test_inbound_contact_message_is_one_channel_message_and_one_ai_message():
    message = _message()

    channel, platform = usage_from_message(message)

    assert (channel.kind, channel.provider, channel.sku, channel.unit) == ("channel", "whatsapp_evolution", "message.inbound", "message")
    assert (platform.kind, platform.provider, platform.sku) == ("platform", "flowsdone", "ai_message")
    assert platform.channel_type == "whatsapp_evolution"
    assert channel.quantity == platform.quantity == Decimal(1)
    assert channel.tenant_id == message.tenant_id and channel.conversation_id == message.conversation_id
    assert channel.event_id != platform.event_id


def test_outbound_message_is_only_channel_usage():
    [channel] = usage_from_message(_message(direction="outbound", sender_type="bot"))

    assert channel.sku == "message.outbound"


def test_a_refused_inbound_message_is_not_an_ai_message():
    [channel] = usage_from_message(_message(billable=False))

    assert channel.kind == "channel"


def test_event_ids_are_deterministic():
    message = _message()

    assert [e.event_id for e in usage_from_message(message)] == [e.event_id for e in usage_from_message(message)]
    assert usage_event_id("a", "b") == usage_event_id("a", "b") != usage_event_id("a", "c")


@pytest.mark.parametrize("model,provider", [
    ("gpt-4.1-mini-2025-04-14", "openai"),
    ("o4-mini", "openai"),
    ("claude-sonnet-5", "anthropic"),
    ("models/gemini-2.5-flash", "google"),
    ("mistral-large", "mistral"),
    ("something-else", "unknown"),
])
def test_infer_llm_provider(model, provider):
    assert infer_llm_provider(model) == provider


def test_generation_yields_one_event_per_non_zero_token_counter():
    conversation = make_conversation(channel_type="telegram")
    generation = LlmGeneration(
        id="obs-1", trace_id="trace-1", session_id=str(conversation.id), model="gpt-4.1-mini",
        start_time=T0, input_tokens=500, output_tokens=40, cached_input_tokens=0,
    )

    events = usage_from_generation(generation, conversation)

    assert [(e.unit, e.quantity) for e in events] == [("input_token", Decimal(500)), ("output_token", Decimal(40))]
    assert all(e.kind == "llm" and e.provider == "openai" and e.sku == "gpt-4.1-mini" for e in events)
    assert all(e.tenant_id == conversation.tenant_id and e.conversation_id == conversation.id for e in events)
    assert all(e.trace_id == "trace-1" and e.channel_type == "telegram" for e in events)
