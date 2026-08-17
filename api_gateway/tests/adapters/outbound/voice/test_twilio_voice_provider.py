"""Tests for TwilioVoiceProviderAdapter."""

from __future__ import annotations

import json

import pytest
from twilio.request_validator import RequestValidator

from app.adapters.outbound.voice.twilio_voice_provider import (
    TwilioVoiceProviderAdapter,
)

AUTH_TOKEN = "test-auth-token"
URL = "https://platform.flowsdone.com/webhooks/voice"
PARAMS = {"CallSid": "CA123", "From": "+15550001111", "To": "+15559998888"}


def _valid_signature() -> str:
    return RequestValidator(AUTH_TOKEN).compute_signature(URL, PARAMS)


def test_verify_webhook_signature_accepts_a_valid_signature():
    provider = TwilioVoiceProviderAdapter()

    assert provider.verify_webhook_signature(
        url=URL, form_params=PARAMS, signature=_valid_signature(), auth_token=AUTH_TOKEN
    )


def test_verify_webhook_signature_rejects_a_wrong_signature():
    provider = TwilioVoiceProviderAdapter()

    assert not provider.verify_webhook_signature(
        url=URL, form_params=PARAMS, signature="not-a-real-signature", auth_token=AUTH_TOKEN
    )


def test_verify_webhook_signature_rejects_missing_signature_or_token():
    provider = TwilioVoiceProviderAdapter()

    assert not provider.verify_webhook_signature(
        url=URL, form_params=PARAMS, signature="", auth_token=AUTH_TOKEN
    )
    assert not provider.verify_webhook_signature(
        url=URL, form_params=PARAMS, signature=_valid_signature(), auth_token=""
    )


def test_build_twiml_connect_embeds_the_stream_url():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_twiml_connect(stream_url="wss://platform.flowsdone.com/voice/stream/CA123")

    assert "<ConversationRelay" in twiml
    assert 'url="wss://platform.flowsdone.com/voice/stream/CA123"' in twiml
    assert "<Connect>" in twiml


def test_build_twiml_connect_embeds_voice_language_and_tts_provider_when_given():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_twiml_connect(
        stream_url="wss://platform.flowsdone.com/voice/stream/CA123",
        voice="Google.es-US-Neural2-A",
        language="es-MX",
        tts_provider="Google",
    )

    assert 'voice="Google.es-US-Neural2-A"' in twiml
    assert 'language="es-MX"' in twiml
    assert 'ttsProvider="Google"' in twiml


def test_build_twiml_connect_omits_voice_attributes_when_not_given():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_twiml_connect(stream_url="wss://platform.flowsdone.com/voice/stream/CA123")

    assert "voice=" not in twiml
    assert "ttsProvider=" not in twiml


def test_build_twiml_connect_embeds_action_url_when_given():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_twiml_connect(
        stream_url="wss://platform.flowsdone.com/voice/stream/CA123",
        action_url="https://platform.flowsdone.com/webhooks/voice/handoff",
    )

    assert 'action="https://platform.flowsdone.com/webhooks/voice/handoff"' in twiml
    assert 'method="POST"' in twiml


def test_build_twiml_connect_omits_action_when_not_given():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_twiml_connect(stream_url="wss://platform.flowsdone.com/voice/stream/CA123")

    assert "action=" not in twiml


def test_build_relay_end_frame_json_encodes_handoff_data():
    provider = TwilioVoiceProviderAdapter()

    frame = provider.build_relay_end_frame(
        handoff_data={"reason": "human_transfer", "transfer_number": "+34601491522"}
    )

    assert frame["type"] == "end"
    assert json.loads(frame["handoffData"]) == {
        "reason": "human_transfer",
        "transfer_number": "+34601491522",
    }


def test_build_handoff_twiml_dials_the_given_number():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_handoff_twiml(phone_number="+34601491522")

    assert "<Dial>+34601491522</Dial>" in twiml


def test_build_handoff_twiml_includes_caller_id_when_given():
    provider = TwilioVoiceProviderAdapter()

    twiml = provider.build_handoff_twiml(phone_number="+34601491522", caller_id="+16014944500")

    assert 'callerId="+16014944500"' in twiml
    assert "<Dial" in twiml and "+34601491522</Dial>" in twiml


def test_parse_relay_frame_normalizes_a_setup_frame():
    provider = TwilioVoiceProviderAdapter()

    event = provider.parse_relay_frame({"type": "setup", "callSid": "CA123", "from": "+1555"})

    assert event.type == "setup"
    assert event.call_sid == "CA123"
    assert event.text is None


def test_parse_relay_frame_normalizes_a_prompt_frame_with_text():
    provider = TwilioVoiceProviderAdapter()

    event = provider.parse_relay_frame(
        {"type": "prompt", "callSid": "CA123", "voicePrompt": "hola, quiero soporte"}
    )

    assert event.type == "prompt"
    assert event.text == "hola, quiero soporte"


def test_parse_relay_frame_normalizes_a_dtmf_frame():
    provider = TwilioVoiceProviderAdapter()

    event = provider.parse_relay_frame({"type": "dtmf", "callSid": "CA123", "digit": "5"})

    assert event.type == "dtmf"
    assert event.text == "5"


def test_parse_relay_frame_rejects_an_unknown_frame_type():
    provider = TwilioVoiceProviderAdapter()

    with pytest.raises(ValueError):
        provider.parse_relay_frame({"type": "something-new", "callSid": "CA123"})


def test_build_relay_text_frame_shape():
    provider = TwilioVoiceProviderAdapter()

    frame = provider.build_relay_text_frame(text="hola, ¿en qué puedo ayudarte?")

    assert frame == {"type": "text", "token": "hola, ¿en qué puedo ayudarte?", "last": True}


def test_build_relay_text_frame_respects_last_false():
    provider = TwilioVoiceProviderAdapter()

    frame = provider.build_relay_text_frame(text="procesando", last=False)

    assert frame["last"] is False
