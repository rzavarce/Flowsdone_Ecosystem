"""Tests for ChannelSenderFactory and WebhookRegistrarFactory.

Mostly smoke tests: these factories are plain wiring, so what matters
is that every channel_type that shows up elsewhere in the codebase
(inbound webhooks, ChannelType literal) actually gets an entry, and
that WebhookRegistrarFactory's entries have the secret_field contract
right for each platform.
"""

from __future__ import annotations

from app.adapters.outbound.channels.factory import ChannelSenderFactory
from app.adapters.outbound.channels.meta_webhook_registrar import MetaWebhookRegistrar
from app.adapters.outbound.channels.telegram_webhook_registrar import (
    TelegramWebhookRegistrar,
)
from app.adapters.outbound.channels.twilio_voice_sender import TwilioVoiceSender
from app.adapters.outbound.channels.webhook_registrar_factory import (
    WebhookRegistrarFactory,
)
from app.application.services.ws_registry import WSRegistry
from app.domain.models.channel_connection import ChannelType

ALL_CHANNEL_TYPES = set(ChannelType.__args__)


def test_channel_sender_factory_covers_every_channel_type():
    senders = ChannelSenderFactory().build_all()

    assert set(senders.keys()) == ALL_CHANNEL_TYPES


def test_channel_sender_factory_wires_voice_dependencies_into_its_sender():
    call_session_registry = WSRegistry()

    senders = ChannelSenderFactory().build_all(
        call_session_registry=call_session_registry, voice_provider="a-voice-provider"
    )

    voice_sender = senders["voice"]
    assert isinstance(voice_sender, TwilioVoiceSender)
    assert voice_sender._call_session_registry is call_session_registry
    assert voice_sender._voice_provider == "a-voice-provider"


def test_webhook_registrar_factory_covers_the_auto_registered_channels():
    registrars = WebhookRegistrarFactory().build_all()

    assert set(registrars.keys()) == {"telegram", "facebook", "instagram"}
    assert isinstance(registrars["telegram"], TelegramWebhookRegistrar)
    assert isinstance(registrars["facebook"], MetaWebhookRegistrar)
    assert isinstance(registrars["instagram"], MetaWebhookRegistrar)


def test_telegram_needs_a_generated_secret_meta_channels_do_not():
    registrars = WebhookRegistrarFactory().build_all()

    assert registrars["telegram"].secret_field == "telegram_webhook_secret"
    assert registrars["facebook"].secret_field is None
    assert registrars["instagram"].secret_field is None


def test_facebook_and_instagram_subscribe_to_different_fields():
    registrars = WebhookRegistrarFactory().build_all()

    assert "messaging_postbacks" in registrars["facebook"]._subscribed_fields
    assert registrars["instagram"]._subscribed_fields == "messages"
