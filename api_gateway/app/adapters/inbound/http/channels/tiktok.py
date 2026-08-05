"""TikTok inbound webhook."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from .....application.use_cases.route_channel_message import ChannelMessageNotRoutable

logger = logging.getLogger("channels.tiktok")

router = APIRouter(prefix="/webhooks/tiktok", tags=["channels:tiktok"])

CHANNEL_TYPE = "tiktok"
APP_PROVIDER = "tiktok"


def _verify_signature(raw_body: bytes, signature_header: str | None, client_secret: str | None) -> bool:
    """Verify TikTok's webhook signature.

    TikTok signs its webhooks with the `TikTok-Signature: t=<ts>,s=<sig>`
    header, where sig = HMAC-SHA256(client_secret, f"{ts}.{raw_body}")
    in hex.

    Args:
        raw_body (bytes): Raw request body bytes.
        signature_header (str | None): Value of the TikTok-Signature header.
        client_secret (str | None): The app's client secret to validate against.

    Returns:
        bool: True if the signature is present and valid.
    """
    if not signature_header or not client_secret:
        return False

    parts = dict(
        item.split("=", 1) for item in signature_header.split(",") if "=" in item
    )
    timestamp, signature = parts.get("t"), parts.get("s")
    if not timestamp or not signature:
        return False

    message = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected = hmac.new(
        client_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


@router.post("")
async def receive_webhook(request: Request) -> JSONResponse:
    """Receive a TikTok webhook event and route the message.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        JSONResponse: Acknowledges the event to TikTok.
    """
    raw_body = await request.body()
    signature = request.headers.get("TikTok-Signature")

    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    client_secret = channel_app.credentials.get("client_secret") if channel_app else None

    if not _verify_signature(raw_body, signature, client_secret):
        logger.warning("channels.tiktok.invalid_signature")
        return JSONResponse(status_code=401, content={"status": "invalid_signature"})

    body = await request.json()
    route_use_case = request.app.state.route_channel_message_use_case

    data = body.get("data") or {}
    open_id = data.get("open_id")
    text = data.get("message") or data.get("content")

    if open_id and text:
        await _route_event(route_use_case, open_id, text, body)

    return JSONResponse(status_code=200, content={"status": "ok"})


async def _route_event(
    route_use_case: Any,
    open_id: str,
    text: str,
    raw_event: Dict[str, Any],
) -> None:
    """Route a single TikTok message to its Langflow agent.

    Args:
        route_use_case (Any): The RouteChannelMessageUseCase instance.
        open_id (str): TikTok open_id, used as both external_id and
            sender_id.
        text (str): Message text.
        raw_event (Dict[str, Any]): The raw TikTok event, kept in the
            payload for debugging.
    """
    try:
        await route_use_case.execute(
            channel_type=CHANNEL_TYPE,
            external_id=open_id,
            external_conversation_key=open_id,
            sender_id=open_id,
            payload={"message": text, "raw": raw_event},
        )
    except ChannelMessageNotRoutable:
        logger.warning("channels.tiktok.not_routable", extra={"open_id": open_id})
    except Exception:
        logger.exception("channels.tiktok.routing_failed")
