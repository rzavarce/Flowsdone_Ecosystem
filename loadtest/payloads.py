"""Payload builders for the WhatsApp (Evolution API) webhook load test.

Kept separate from ``locustfile.py`` so the payload shape can be unit-tested
without spinning up Locust, and reused by the chaos scripts if needed.
"""

from __future__ import annotations

import random
import time
import uuid


def build_whatsapp_webhook_payload(instance: str, sender_suffix: str | None = None) -> dict:
    """Build a minimal valid Evolution API ``messages.upsert`` webhook body.

    Mirrors exactly what ``api_gateway/app/adapters/inbound/http/channels/whatsapp_evolution.py``
    reads: ``event``, ``instance``, ``data.key.remoteJid``, ``data.key.fromMe``,
    and ``data.message.conversation``. Every other field Evolution API sends in
    real life is irrelevant to the gateway and intentionally omitted.

    Args:
        instance: The Evolution API instance name — must match the
            ``external_id`` of a ``channel_connection`` row with
            ``channel_type="whatsapp_evolution"`` for the message to route
            anywhere past the webhook (see ``setup_test_tenant.py``).
        sender_suffix: Optional fixed suffix for the simulated phone number,
            so a single Locust user can reuse one conversation across
            requests instead of opening a new one each time. A random one is
            generated when omitted, simulating many distinct end users.

    Returns:
        A JSON-serializable dict ready to POST to ``/webhooks/whatsapp``.
    """
    suffix = sender_suffix or f"{random.randint(10_000_000, 99_999_999)}"
    remote_jid = f"549{suffix}@s.whatsapp.net"
    return {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": False,
                "id": f"LOADTEST-{uuid.uuid4().hex[:16].upper()}",
            },
            "message": {
                "conversation": f"[loadtest] mensaje de prueba enviado a las {time.time():.3f}",
            },
            "messageTimestamp": int(time.time()),
        },
    }
