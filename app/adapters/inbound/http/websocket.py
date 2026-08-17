"""Webchat WebSocket endpoint."""

import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Handle a webchat WebSocket connection end to end.

    The first frame must carry a conversation_id (top-level or inside
    "payload"); the connection is registered in WSRegistry under that
    id so HandleOutboundResponseUseCase can push responses back to it.
    Subsequent frames are treated as chat messages unless they are a
    "ping" (answered with "pong") or a registration-only frame.

    Args:
        ws (WebSocket): The FastAPI WebSocket connection.
    """
    correlation_id = str(uuid4())
    conversation_id = None

    await ws.accept()

    try:
        first_frame = await ws.receive_json()

        conversation_id = (
            first_frame.get("conversation_id")
            or (first_frame.get("payload") or {}).get("conversation_id")
        )

        if not conversation_id:
            await ws.send_json(
                {
                    "type": "error",
                    "error": "missing_conversation_id",
                }
            )
            await ws.close(code=1008)
            return

        ws.app.state.ws_registry.add(conversation_id, ws)

        logger.info(
            "websocket.connected",
            extra={
                "correlation_id": correlation_id,
                "conversation_id": conversation_id,
            },
        )

        await ws.send_json(
            {
                "type": "connected",
                "conversation_id": conversation_id,
            }
        )

        # The first frame may already be a user message.
        await _maybe_ingest_message(ws, first_frame, conversation_id, correlation_id)

        # Keep the socket alive and process subsequent frames.
        while True:
            frame = await ws.receive_json()

            if frame.get("type") == "ping":
                await ws.send_json({"type": "pong"})
                continue

            await _maybe_ingest_message(ws, frame, conversation_id, correlation_id)

    except WebSocketDisconnect:
        logger.info(
            "websocket.disconnected",
            extra={
                "correlation_id": correlation_id,
                "conversation_id": conversation_id,
            },
        )
    except Exception:
        logger.error(
            "websocket.processing.failed",
            extra={
                "correlation_id": correlation_id,
                "conversation_id": conversation_id,
            },
            exc_info=True,
        )
    finally:
        if conversation_id:
            ws.app.state.ws_registry.remove(conversation_id)


async def _maybe_ingest_message(
    ws: WebSocket,
    frame: dict,
    conversation_id: str,
    correlation_id: str,
) -> None:
    """Convert a WebSocket frame into a canonical message and ingest it.

    No-ops for registration-only frames (connect/init/register without
    a message). Sends an error frame back to the client if the frame is
    missing workflow_id or message text.

    Args:
        ws (WebSocket): The FastAPI WebSocket connection.
        frame (dict): The decoded JSON frame received from the client.
        conversation_id (str): Id of this connection's conversation.
        correlation_id (str): Id used to correlate log lines for this connection.
    """
    frame_type = frame.get("type")
    payload = frame.get("payload") or {}

    is_registration_only = (
        frame_type in {"connect", "init", "register"}
        and not payload.get("message")
        and not frame.get("message")
    )

    if is_registration_only:
        return

    workflow_id = frame.get("workflow_id") or payload.get("workflow_id")
    sender_id = frame.get("sender_id") or payload.get("sender_id") or "webchat"
    transport = frame.get("transport") or "rabbitmq"
    channel = frame.get("channel") or "websocket"

    # Accept the message either at the top level or inside "payload".
    message_text = payload.get("message") or frame.get("message")

    if not workflow_id:
        await ws.send_json(
            {
                "type": "error",
                "error": "missing_workflow_id",
            }
        )
        return

    if not message_text:
        await ws.send_json(
            {
                "type": "error",
                "error": "missing_message",
            }
        )
        return

    normalized_payload = dict(payload)
    normalized_payload["message"] = message_text
    normalized_payload["conversation_id"] = conversation_id

    logger.info(
        "websocket.message.received",
        extra={
            "correlation_id": correlation_id,
            "conversation_id": conversation_id,
            "workflow_id": workflow_id,
        },
    )

    ingest_use_case = ws.app.state.ingest_message_use_case

    await ingest_use_case.execute(
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        transport=transport,
        payload=normalized_payload,
        channel=channel,
    )

    await ws.send_json(
        {
            "type": "accepted",
            "conversation_id": conversation_id,
        }
    )
