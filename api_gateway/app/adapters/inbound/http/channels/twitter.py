"""X (Twitter) inbound webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from api_gateway.app.application.services.switchboard import ChannelMessageNotRoutable

logger = logging.getLogger("channels.twitter")

router = APIRouter(prefix="/webhooks/twitter", tags=["channels:twitter"])

CHANNEL_TYPE = "twitter"
APP_PROVIDER = "twitter"


def _hmac_sha256_base64(secret: str, message: str) -> str:
    """Compute a base64-encoded HMAC-SHA256 digest.

    Args:
        secret (str): HMAC secret key.
        message (str): Message to sign.

    Returns:
        str: The base64-encoded digest.
    """
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@router.get("")
async def crc_challenge(request: Request) -> JSONResponse:
    """Validate the X/Twitter Account Activity API webhook subscription.

    Responds with an HMAC-SHA256 of the crc_token, signed with the
    consumer secret, as required by X's CRC challenge.

    Args:
        request (Request): The incoming FastAPI request; carries the
            crc_token query parameter.

    Returns:
        JSONResponse: The signed response_token.

    Raises:
        HTTPException: 400 if crc_token or the consumer secret is missing.
    """
    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    consumer_secret = channel_app.credentials.get("consumer_secret") if channel_app else None

    crc_token = request.query_params.get("crc_token")
    if not crc_token or not consumer_secret:
        raise HTTPException(status_code=400, detail="missing crc_token or consumer secret")

    response_token = "sha256=" + _hmac_sha256_base64(consumer_secret, crc_token)
    return JSONResponse(status_code=200, content={"response_token": response_token})


@router.post("")
async def receive_webhook(request: Request) -> JSONResponse:
    """Receive an X Account Activity webhook event and route each DM.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        JSONResponse: Acknowledges the event to X.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Twitter-Webhooks-Signature")

    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    consumer_secret = channel_app.credentials.get("consumer_secret") if channel_app else None

    if not _verify_signature(raw_body, signature, consumer_secret):
        logger.warning("channels.twitter.invalid_signature")
        return JSONResponse(status_code=401, content={"status": "invalid_signature"})

    body = await request.json()
    switchboard = request.app.state.switchboard

    account_id = body.get("for_user_id")

    for event in body.get("direct_message_events", []):
        message_create = event.get("message_create") or {}
        sender_id = message_create.get("sender_id")
        text = (message_create.get("message_data") or {}).get("text")

        if not account_id or not sender_id or not text:
            continue

        await _route_event(switchboard, account_id, sender_id, text, event)

    return JSONResponse(status_code=200, content={"status": "ok"})


def _verify_signature(raw_body: bytes, signature_header: str | None, consumer_secret: str | None) -> bool:
    """Verify X's X-Twitter-Webhooks-Signature header.

    Args:
        raw_body (bytes): Raw request body bytes.
        signature_header (str | None): Value of the
            X-Twitter-Webhooks-Signature header.
        consumer_secret (str | None): The app's consumer secret to
            validate against.

    Returns:
        bool: True if the signature is present and valid.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not consumer_secret:
        return False

    expected = "sha256=" + _hmac_sha256_base64(consumer_secret, raw_body.decode("utf-8"))
    return hmac.compare_digest(expected, signature_header)


async def _route_event(
    switchboard: Any,
    account_id: str,
    sender_id: str,
    text: str,
    raw_event: Dict[str, Any],
) -> None:
    """Route a single X direct message to its currently assigned app.

    Args:
        switchboard (Any): The Switchboard instance.
        account_id (str): X account id the DM was sent to.
        sender_id (str): Id of the sender.
        text (str): Message text.
        raw_event (Dict[str, Any]): The raw X event, kept in the
            payload for debugging.
    """
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=account_id,
            external_conversation_key=sender_id,
            sender_id=sender_id,
            message_text=text,
            raw_payload=raw_event,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.twitter.not_routable",
            extra={"account_id": account_id, "sender_id": sender_id},
        )
    except Exception:
        logger.exception("channels.twitter.routing_failed")
