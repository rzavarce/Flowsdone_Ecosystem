"""Sanity tests for the load-test payload builder.

Guards against silently drifting out of sync with what
``adapters/inbound/http/channels/whatsapp_evolution.py`` actually reads —
if that handler's expected shape ever changes, these should fail loudly
instead of the load test just silently generating 100% ``ignored`` traffic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from payloads import build_whatsapp_webhook_payload


def test_payload_has_fields_the_webhook_handler_reads():
    payload = build_whatsapp_webhook_payload("my-instance")

    assert payload["event"] == "messages.upsert"
    assert payload["instance"] == "my-instance"
    assert payload["data"]["key"]["fromMe"] is False
    assert payload["data"]["key"]["remoteJid"].endswith("@s.whatsapp.net")
    assert isinstance(payload["data"]["message"]["conversation"], str)
    assert payload["data"]["message"]["conversation"]


def test_two_calls_generate_distinct_senders_by_default():
    a = build_whatsapp_webhook_payload("my-instance")
    b = build_whatsapp_webhook_payload("my-instance")
    assert a["data"]["key"]["remoteJid"] != b["data"]["key"]["remoteJid"]
    assert a["data"]["key"]["id"] != b["data"]["key"]["id"]


def test_sender_suffix_pins_the_conversation():
    a = build_whatsapp_webhook_payload("my-instance", sender_suffix="12345678")
    b = build_whatsapp_webhook_payload("my-instance", sender_suffix="12345678")
    assert a["data"]["key"]["remoteJid"] == b["data"]["key"]["remoteJid"] == "54912345678@s.whatsapp.net"
