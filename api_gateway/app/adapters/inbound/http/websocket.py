import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    correlation_id = str(uuid4())
    conversation_id = None

    await ws.accept()

    try:
        # ----------------------------------------------------------
        # 1. Primer frame obligatorio: debe traer conversation_id
        # ----------------------------------------------------------
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

        # ACK de conexión
        await ws.send_json(
            {
                "type": "connected",
                "conversation_id": conversation_id,
            }
        )

        # ----------------------------------------------------------
        # 2. Si el primer frame ya es un mensaje de usuario, lo procesamos
        # ----------------------------------------------------------
        await _maybe_ingest_message(ws, first_frame, conversation_id, correlation_id)

        # ----------------------------------------------------------
        # 3. Mantener socket vivo y procesar frames posteriores
        # ----------------------------------------------------------
        while True:
            frame = await ws.receive_json()

            # ping opcional
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
    """
    Convierte un frame WS en mensaje canónico y lo inyecta al pipeline Rabbit.
    No toca Kafka.
    """

    # ----------------------------------------------------------
    # Ignorar frames solo de registro
    # ----------------------------------------------------------
    frame_type = frame.get("type")
    payload = frame.get("payload") or {}

    is_registration_only = (
        frame_type in {"connect", "init", "register"}
        and not payload.get("message")
        and not frame.get("message")
    )

    if is_registration_only:
        return

    # ----------------------------------------------------------
    # Extraer datos
    # ----------------------------------------------------------
    workflow_id = frame.get("workflow_id") or payload.get("workflow_id")
    sender_id = frame.get("sender_id") or payload.get("sender_id") or "webchat"
    transport = frame.get("transport") or "rabbitmq"
    channel = frame.get("channel") or "websocket"

    # Compatibilidad: permitir message directo o dentro de payload
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

    # ----------------------------------------------------------
    # Inyectar al pipeline usando el use case ya existente
    # ----------------------------------------------------------
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