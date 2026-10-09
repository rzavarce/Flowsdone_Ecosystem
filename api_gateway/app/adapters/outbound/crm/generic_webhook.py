"""Generic webhook CRM provider: signed JSON events POSTed to a URL the
client chooses; the client's software replies and closes through the
Flowsdone CRM API.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict

import httpx

from app.core.config import settings
from app.domain.models.crm import CrmEvent, CrmIntegration
from app.domain.ports.outbound import CrmDeliveryError, CrmProviderPort

logger = logging.getLogger("crm.generic_webhook")

SIGNATURE_HEADER = "X-Flowsdone-Signature"
TIMESTAMP_HEADER = "X-Flowsdone-Timestamp"

# Statuses worth retrying: the receiver is down, overloaded or rate-limiting.
_RETRYABLE = {408, 425, 429}


def signature(secret: str, timestamp: str, body: bytes) -> str:
    """Signature of one delivery, as the receiver must recompute it.

    Args:
        secret (str): The integration's signing_secret.
        timestamp (str): Value of the X-Flowsdone-Timestamp header (Unix seconds).
        body (bytes): The raw request body.

    Returns:
        str: "sha256=" + hex HMAC-SHA256 of "{timestamp}.{body}".
    """
    digest = hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def event_body(event: CrmEvent) -> Dict[str, Any]:
    """The JSON document sent for an event (the public webhook contract).

    Args:
        event (CrmEvent): The event.

    Returns:
        Dict[str, Any]: The body, including where to reply and close.
    """
    api = f"{settings.PUBLIC_BASE_URL}/integrations/crm/{event.integration_id}"
    return {
        "id": str(event.id),
        "type": event.type,
        "occurred_at": event.occurred_at.isoformat(),
        "conversation_id": event.conversation_id,
        "handoff_id": str(event.handoff_id),
        "data": event.data,
        "reply_url": f"{api}/messages",
        "close_url": f"{api}/close",
    }


class GenericWebhookProvider(CrmProviderPort):
    """POSTs each event, signed, to the integration's `config.url`."""

    def __init__(self, *, ensure_allowed: Callable[[str], Awaitable[None]], timeout_seconds: float = 10.0) -> None:
        """Build the provider.

        Args:
            ensure_allowed (Callable[[str], Awaitable[None]]): Refuses
                destinations that are not allowed (https, public addresses
                only - same rules as the workflow callbacks).
            timeout_seconds (float): Per-request timeout.
        """
        self._ensure_allowed = ensure_allowed
        self._timeout = timeout_seconds

    async def deliver(self, event: CrmEvent, integration: CrmIntegration) -> None:
        """POST one event to the client's URL.

        Args:
            event (CrmEvent): The event.
            integration (CrmIntegration): Holds `config.url` and
                `credentials.signing_secret`.

        Raises:
            CrmDeliveryError: On network errors, timeouts, 5xx, 408, 425 or 429.
            ValueError: If the integration has no URL/secret, the URL is not
                allowed, or the receiver rejects the event (other 4xx).
        """
        url = integration.config.get("url")
        secret = integration.credentials.get("signing_secret")
        if not url or not secret:
            raise ValueError("the integration has no url or signing_secret")
        await self._ensure_allowed(url)

        body = json.dumps(event_body(event), separators=(",", ":"), sort_keys=True).encode("utf-8")
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Flowsdone-Event": event.type,
            "X-Flowsdone-Event-Id": str(event.id),
            TIMESTAMP_HEADER: timestamp,
            SIGNATURE_HEADER: signature(secret, timestamp, body),
        }

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
            try:
                response = await client.post(url, content=body, headers=headers)
            except httpx.HTTPError as exc:
                raise CrmDeliveryError(f"could not reach the CRM: {exc}") from exc

        if response.status_code >= 500 or response.status_code in _RETRYABLE:
            raise CrmDeliveryError(f"the CRM answered {response.status_code}")
        if response.status_code >= 400:
            raise ValueError(f"the CRM rejected the event ({response.status_code}): {response.text[:200]}")
