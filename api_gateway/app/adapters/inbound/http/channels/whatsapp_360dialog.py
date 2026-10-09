"""WhatsApp (360dialog, official Cloud API) inbound webhook."""

from __future__ import annotations

import hmac
import logging
from typing import Any, Dict, Iterator, Optional, Tuple

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from app.adapters.outbound.channels.d360_api import WEBHOOK_SECRET_FIELD, WEBHOOK_SECRET_HEADER
from app.application.services.switchboard import ChannelMessageNotRoutable
from app.domain.models.conversation_contact import SenderProfile

logger = logging.getLogger("channels.whatsapp_360dialog")

router = APIRouter(prefix="/webhooks/whatsapp-360dialog", tags=["channels:whatsapp"])

CHANNEL_TYPE = "whatsapp_360dialog"


def _message_text(message: Dict[str, Any]) -> Optional[str]:
    """The text a Cloud API message carries, for the types the bot understands.

    Args:
        message (Dict[str, Any]): One item of `value.messages`.

    Returns:
        Optional[str]: The typed text, the tapped button's text or the
        chosen reply/list option's title; None for any other type
        (media, location, reactions, ...).
    """
    kind = message.get("type")
    if kind == "text":
        return (message.get("text") or {}).get("body")
    if kind == "button":
        return (message.get("button") or {}).get("text")
    if kind == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title")
    return None


def _inbound_messages(body: Dict[str, Any]) -> Iterator[Tuple[Dict[str, Any], Dict[str, str]]]:
    """Walk a Cloud API webhook body and yield every inbound message.

    Status updates (sent/delivered/read/failed) come in the same
    envelope under `value.statuses` and are skipped.

    Args:
        body (Dict[str, Any]): The webhook JSON body.

    Yields:
        Tuple[Dict[str, Any], Dict[str, str]]: Each message, with the
        `wa_id -> profile name` map of its change.
    """
    for entry in body.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field", "messages") != "messages":
                continue
            value = change.get("value") or {}
            names = {
                str(c.get("wa_id")): ((c.get("profile") or {}).get("name") or "").strip()
                for c in value.get("contacts") or []
                if c.get("wa_id")
            }
            for message in value.get("messages") or []:
                yield message, names


def _sender_profile(wa_id: str, name: Optional[str]) -> SenderProfile:
    """What a Cloud API message says about its sender.

    Args:
        wa_id (str): The sender's WhatsApp id (the number, digits only).
        name (Optional[str]): The name on the sender's WhatsApp profile.

    Returns:
        SenderProfile: The number in "+<digits>" form and the profile name.
    """
    return SenderProfile(name=name or None, phone=f"+{wa_id}" if wa_id.isdigit() else None)


@router.post("/{external_id}")
async def receive_webhook(external_id: str, request: Request) -> JSONResponse:
    """Receive a 360dialog webhook call and route each inbound message.

    Args:
        external_id (str): The connection's business number, taken from
            the path (it is the URL the registrar configured).
        request (Request): The incoming FastAPI request; must carry the
            connection's secret in the X-Flowsdone-Webhook-Secret header.

    Returns:
        JSONResponse: 200 once handled (also for a number that is no
        longer connected, so 360dialog stops retrying), 401 if the
        secret is wrong.
    """
    resolution = await request.app.state.channel_connection_repo.get_by_channel_and_external_id(
        CHANNEL_TYPE, external_id
    )
    if resolution is None:
        logger.warning("channels.whatsapp_360dialog.unknown_number", extra={"external_id": external_id})
        return JSONResponse(status_code=200, content={"status": "ignored"})

    expected = resolution.credentials.get(WEBHOOK_SECRET_FIELD) or ""
    received = request.headers.get(WEBHOOK_SECRET_HEADER) or ""
    if not expected or not hmac.compare_digest(received.encode(), expected.encode()):
        logger.warning("channels.whatsapp_360dialog.invalid_secret", extra={"external_id": external_id})
        return JSONResponse(status_code=401, content={"status": "invalid_secret"})

    body = await request.json()
    switchboard = request.app.state.switchboard

    for message, names in _inbound_messages(body):
        wa_id = str(message.get("from") or "")
        text = _message_text(message)
        if not wa_id or not text:
            continue
        await _route_event(switchboard, external_id, wa_id, text, message, _sender_profile(wa_id, names.get(wa_id)))

    return JSONResponse(status_code=200, content={"status": "ok"})


async def _route_event(
    switchboard: Any,
    external_id: str,
    wa_id: str,
    text: str,
    raw_message: Dict[str, Any],
    sender_profile: Optional[SenderProfile] = None,
) -> None:
    """Route a single WhatsApp message to its currently assigned app.

    Args:
        switchboard (Any): The Switchboard instance.
        external_id (str): The connection's business number.
        wa_id (str): WhatsApp id of the sender (also the conversation key
            and the recipient of the replies).
        text (str): Message text.
        raw_message (Dict[str, Any]): The raw Cloud API message, kept in
            the payload for debugging.
        sender_profile (Optional[SenderProfile]): Number and name of the
            sender, for their contact card.
    """
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=external_id,
            external_conversation_key=wa_id,
            sender_id=wa_id,
            message_text=text,
            raw_payload=raw_message,
            sender_profile=sender_profile,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.whatsapp_360dialog.not_routable",
            extra={"external_id": external_id, "wa_id": wa_id},
        )
    except Exception:
        logger.exception("channels.whatsapp_360dialog.routing_failed")
