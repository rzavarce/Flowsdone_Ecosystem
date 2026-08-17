"""Facebook Messenger inbound webhook."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, PlainTextResponse

from app.application.services.switchboard import ChannelMessageNotRoutable
from app.adapters.inbound.http.channels.meta_common import handle_verification_challenge, verify_meta_signature

logger = logging.getLogger("channels.facebook")

router = APIRouter(prefix="/webhooks/facebook", tags=["channels:facebook"])

CHANNEL_TYPE = "facebook"
# Facebook and Instagram share a single Meta app (see README section 9
# and /internal/admin/channel-apps) - it is not per tenant, it is the
# SaaS's own app.
APP_PROVIDER = "meta"


@router.get("")
async def verify_webhook(request: Request) -> PlainTextResponse:
    """Handle Meta's webhook subscription verification GET request.

    Args:
        request (Request): The incoming FastAPI request; carries the
            hub.mode/hub.verify_token/hub.challenge query parameters.

    Returns:
        PlainTextResponse: Echoes the challenge if verification succeeds.
    """
    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    verify_token = channel_app.credentials.get("webhook_verify_token") if channel_app else None

    params = request.query_params
    return handle_verification_challenge(
        mode=params.get("hub.mode"),
        verify_token=params.get("hub.verify_token"),
        challenge=params.get("hub.challenge"),
        expected_token=verify_token,
    )


@router.post("")
async def receive_webhook(request: Request) -> JSONResponse:
    """Receive a Facebook Messenger webhook event and route each message.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        JSONResponse: Acknowledges the event to Meta.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    app_secret = channel_app.credentials.get("app_secret") if channel_app else None

    if not verify_meta_signature(raw_body, signature, app_secret or ""):
        logger.warning("channels.facebook.invalid_signature")
        return JSONResponse(status_code=401, content={"status": "invalid_signature"})

    body = await request.json()
    switchboard = request.app.state.switchboard

    for entry in body.get("entry", []):
        page_id = entry.get("id")
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            text = message.get("text")
            sender_id = (event.get("sender") or {}).get("id")

            if not page_id or not sender_id or not text:
                continue

            await _route_event(switchboard, page_id, sender_id, text, event)

    # Meta expects 200 + this exact body whenever the signature is
    # valid, so it does not retry indefinitely over *our* routing
    # failures.
    return JSONResponse(status_code=200, content={"status": "EVENT_RECEIVED"})


async def _route_event(
    switchboard: Any,
    page_id: str,
    sender_id: str,
    text: str,
    raw_event: Dict[str, Any],
) -> None:
    """Route a single Messenger message to its currently assigned app.

    Args:
        switchboard (Any): The Switchboard instance.
        page_id (str): Facebook page id the message was sent to.
        sender_id (str): Id of the sender (psid).
        text (str): Message text.
        raw_event (Dict[str, Any]): The raw Meta event, kept in the
            payload for debugging.
    """
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=page_id,
            external_conversation_key=sender_id,
            sender_id=sender_id,
            message_text=text,
            raw_payload=raw_event,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.facebook.not_routable",
            extra={"page_id": page_id, "sender_id": sender_id},
        )
    except Exception:
        logger.exception("channels.facebook.routing_failed")
