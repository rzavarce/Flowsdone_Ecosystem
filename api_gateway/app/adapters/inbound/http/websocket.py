"""Web chat WebSocket endpoint (`/ws`).

Two ways in, chosen by the query string (see application/services/webchat.py):

- `?key=wc_...`: a tenant's **webchat channel**. The page must be one of the
  channel's allowed origins. Each message goes through the Switchboard like
  any other channel (conversation, archive, usage, plan limits).
- `?test_token=...`: the **generic demo**, opened by console staff to try one
  agent. The signed token names the agent's flow; messages go straight to it
  and are neither tracked nor billed.

A connection without either is refused before the handshake completes (the
browser gets HTTP 403). Frames keep the widget's format: the first one
carries `conversation_id` - the visitor's id, kept in the browser - and chat
messages carry `payload.message`. Errors are sent as `chat.error`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.services.switchboard import ChannelMessageNotRoutable, build_conversation_id
from app.application.services.webchat import TestTokenClaims, origin_allowed, verify_test_token
from app.core.config import settings
from app.domain.models.channel_connection import WEBCHAT
from app.domain.models.channel_resolution import ChannelResolution

logger = logging.getLogger("ws")
router = APIRouter()

_VISITOR_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


@dataclass(frozen=True)
class WebchatRoute:
    """Where a connection's messages go.

    Attributes:
        channel (Optional[ChannelResolution]): The tenant's webchat channel.
        test (Optional[TestTokenClaims]): The agent under test (demo).
        key (str): Rate-limit scope (channel key, or the tested agent).
    """

    channel: Optional[ChannelResolution] = None
    test: Optional[TestTokenClaims] = None
    key: str = ""
    test_token: str = ""


def _client_ip(ws: WebSocket) -> str:
    """Best-effort client IP (first X-Forwarded-For hop behind Traefik).

    Args:
        ws (WebSocket): The connection.

    Returns:
        str: The IP, or "unknown".
    """
    if settings.AUTH_TRUST_FORWARDED_FOR:
        forwarded = ws.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    return ws.client.host if ws.client else "unknown"


async def _authorize(ws: WebSocket, key: Optional[str], test_token: Optional[str]) -> Optional[WebchatRoute]:
    """Decide whether the connection may open, and where it goes.

    Args:
        ws (WebSocket): The (not yet accepted) connection.
        key (Optional[str]): A webchat channel's public key.
        test_token (Optional[str]): A demo test token.

    Returns:
        Optional[WebchatRoute]: The route, or None to refuse.
    """
    if test_token:
        claims = verify_test_token(test_token, settings.CALLBACK_HMAC_SECRET)
        if claims is None:
            logger.warning("websocket.test_token.invalid")
            return None
        return WebchatRoute(test=claims, key=f"test:{claims.agent_id}", test_token=test_token)
    if key:
        resolution = await ws.app.state.channel_connection_repo.get_by_channel_and_external_id(WEBCHAT, key)
        if resolution is None:
            logger.warning("websocket.channel.unknown_key")
            return None
        if not origin_allowed(resolution.config.get("allowed_origins") or [], ws.headers.get("origin")):
            logger.warning("websocket.channel.origin_refused", extra={"channel_connection_id": str(resolution.channel_connection_id)})
            return None
        return WebchatRoute(channel=resolution, key=key)
    return None


def _registry_id(route: WebchatRoute, visitor_id: str) -> str:
    """Id the socket is registered under, so replies find their way back.

    For a channel it is the Switchboard's session id (replies are delivered
    by conversation); for the demo, a test-only id.

    Args:
        route (WebchatRoute): The connection's route.
        visitor_id (str): The visitor's id.

    Returns:
        str: The registry id.
    """
    if route.channel is not None:
        return build_conversation_id(route.channel.project_id, WEBCHAT, visitor_id)
    return f"test:{route.test.agent_id}:{visitor_id}"  # type: ignore[union-attr]


async def _error(ws: WebSocket, code: str) -> None:
    """Tell the widget something went wrong (shown as a toast).

    Args:
        ws (WebSocket): The connection.
        code (str): Error code.
    """
    await ws.send_json({"type": "chat.error", "error": code})


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, key: Optional[str] = None, test_token: Optional[str] = None) -> None:
    """Handle a web chat connection end to end (see the module docstring).

    Args:
        ws (WebSocket): The FastAPI WebSocket connection.
        key (Optional[str]): A webchat channel's public key (query string).
        test_token (Optional[str]): A demo test token (query string).
    """
    route = await _authorize(ws, key, test_token)
    if route is None:
        await ws.close(code=1008)
        return

    await ws.accept()
    correlation_id = str(uuid4())
    registry_id: Optional[str] = None
    try:
        first_frame = await ws.receive_json()
        visitor_id = first_frame.get("conversation_id") or (first_frame.get("payload") or {}).get("conversation_id")
        if not isinstance(visitor_id, str) or not _VISITOR_ID.match(visitor_id):
            await _error(ws, "missing_conversation_id")
            await ws.close(code=1008)
            return

        registry_id = _registry_id(route, visitor_id)
        ws.app.state.ws_registry.add(registry_id, ws)
        logger.info("websocket.connected", extra={"correlation_id": correlation_id, "mode": "test" if route.test else "channel"})
        await ws.send_json({"type": "connected", "conversation_id": visitor_id})

        frame: Dict[str, Any] = first_frame
        while True:
            if frame.get("type") == "ping":
                await ws.send_json({"type": "pong"})
            else:
                await _handle_message(ws, route, frame, visitor_id, registry_id)
            frame = await ws.receive_json()

    except WebSocketDisconnect:
        logger.info("websocket.disconnected", extra={"correlation_id": correlation_id})
    except Exception:
        logger.error("websocket.processing.failed", extra={"correlation_id": correlation_id}, exc_info=True)
    finally:
        if registry_id:
            ws.app.state.ws_registry.remove(registry_id)


async def _handle_message(ws: WebSocket, route: WebchatRoute, frame: Dict[str, Any], visitor_id: str, registry_id: str) -> None:
    """Validate, rate-limit and route one chat message.

    Args:
        ws (WebSocket): The connection.
        route (WebchatRoute): Where messages go.
        frame (Dict[str, Any]): The received frame.
        visitor_id (str): The visitor's id.
        registry_id (str): Id the socket is registered under.
    """
    payload = frame.get("payload") or {}
    text = payload.get("message") or frame.get("message")
    if not isinstance(text, str) or not text.strip():
        return  # registration-only frame
    text = text.strip()
    if len(text) > settings.WEBCHAT_MAX_MESSAGE_CHARS:
        await _error(ws, "message_too_long")
        return

    throttle = ws.app.state.login_throttle
    bucket = f"webchat:{route.key}:{_client_ip(ws)}"
    if await throttle.failures(bucket) >= settings.WEBCHAT_MAX_MESSAGES_PER_MINUTE:
        await _error(ws, "rate_limited")
        return
    await throttle.record_failure(bucket, window_seconds=60)

    if route.channel is not None:
        try:
            await ws.app.state.switchboard.handle_inbound_turn(
                channel_type=WEBCHAT,
                external_id=route.key,
                external_conversation_key=visitor_id,
                sender_id=visitor_id,
                message_text=text,
                raw_payload={"origin": ws.headers.get("origin")},
            )
        except ChannelMessageNotRoutable:
            await _error(ws, "channel_unavailable")
            return
    else:
        # Re-checked on every message: a demo tab left open must stop
        # working when its token expires.
        if verify_test_token(route.test_token, settings.CALLBACK_HMAC_SECRET) is None:
            await _error(ws, "test_token_expired")
            return
        await ws.app.state.ingest_message_use_case.execute(
            workflow_id=route.test.workflow_id,  # type: ignore[union-attr]
            conversation_id=registry_id,
            sender_id=f"test:{visitor_id}",
            transport=frame.get("transport") or "rabbitmq",
            payload={"message": text, "conversation_id": registry_id},
            channel="webchat-test",
        )
    await ws.send_json({"type": "accepted", "conversation_id": visitor_id})
