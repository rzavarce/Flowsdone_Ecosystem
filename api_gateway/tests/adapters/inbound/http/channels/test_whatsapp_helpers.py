"""Tests for the Evolution API message-text extraction helper."""

from __future__ import annotations

from api_gateway.app.adapters.inbound.http.channels.whatsapp_evolution import _extract_text


def test_extracts_plain_conversation_text():
    assert _extract_text({"conversation": "hola"}) == "hola"


def test_extracts_extended_text_message():
    assert _extract_text({"extendedTextMessage": {"text": "hola con formato"}}) == "hola con formato"


def test_returns_none_for_unrecognized_message_shape():
    assert _extract_text({"imageMessage": {"caption": "foto"}}) is None


def test_returns_none_for_empty_message():
    assert _extract_text({}) is None
