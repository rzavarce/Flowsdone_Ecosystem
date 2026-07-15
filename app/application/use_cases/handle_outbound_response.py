import logging
from typing import Any, Dict, Optional

import httpx

from app.domain.models.message_envelope import MessageEnvelope

logger = logging.getLogger("usecase.handle_outbound_response")


class HandleOutboundResponseUseCase:
    """
    Use case encargado de:
    - procesar la respuesta del workflow (Langflow)
    - construir payload final
    - enviar a callback_url (si existe)
    - opcional: publicar en broker
    """

    def __init__(
        self,
        publisher: Optional[Any] = None,
        ws_registry: Optional[Any] = None,
    ):
        self.publisher = publisher
        self.ws_registry = ws_registry
    

    async def execute(
        self,
        envelope: MessageEnvelope,
        result: Dict[str, Any],
    ) -> None:

        # ----------------------------------------------------------
        # 1. Extraer mensaje de Langflow
        # ----------------------------------------------------------
        try:
            response_message = (
                result["outputs"][0]["outputs"][0]["outputs"]["message"]["message"]
            )
        except Exception:
            logger.error("handle.outbound.invalid_langflow_response", exc_info=True)
            return

        # ----------------------------------------------------------
        # 2. Construir payload final
        # ----------------------------------------------------------
        response_payload = {
            "message": response_message,
        }

        logger.info(
            "handle.outbound.response.built",
            extra={"message_id": envelope.meta.message_id},
        )

        # ----------------------------------------------------------
        # 3. CALLBACK HTTP
        # ----------------------------------------------------------
        callback_url = None

        try:
            callback_url = envelope.payload.get("callback_url")
        except Exception:
            pass

        if callback_url:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        callback_url,
                        json={
                            "conversation_id": envelope.meta.conversation_id,
                            "message": response_message,
                        },
                    )

                logger.info(
                    "handle.outbound.callback.sent",
                    extra={
                        "url": callback_url,
                        "message_id": envelope.meta.message_id,
                    },
                )

            except Exception as e:
                logger.error(
                    "handle.outbound.callback.failed",
                    extra={
                        "url": callback_url,
                        "message_id": envelope.meta.message_id,
                    },
                    exc_info=e,
                )
        else:
            logger.debug(
                "handle.outbound.callback.not_present",
                extra={"message_id": envelope.meta.message_id},
            )

        # ----------------------------------------------------------
        # ✅ 4. WEBSOCKET (AQUÍ VA 🔥)
        # ----------------------------------------------------------
        if getattr(self, "ws_registry", None) and envelope.meta.conversation_id:
            try:
                await self.ws_registry.send(
                    conversation_id=envelope.meta.conversation_id,
                    message=response_payload,
                )

                logger.info(
                    "handle.outbound.ws.sent",
                    extra={
                        "conversation_id": envelope.meta.conversation_id,
                    },
                )

            except Exception:
                logger.error("handle.outbound.ws.failed", exc_info=True)

        # ----------------------------------------------------------
        # 5. Construir envelope
        # ----------------------------------------------------------
        try:
            response_envelope = MessageEnvelope(
                meta=envelope.meta.model_copy(update={"direction": "outbound"}),
                transport=envelope.transport,
                channel=envelope.channel,
                payload=response_payload,
                response_to=envelope.meta.message_id,
            )
        except Exception:
            logger.error("handle.outbound.envelope.build.failed", exc_info=True)
            return

        # ----------------------------------------------------------
        # 6. Publicar en broker
        # ----------------------------------------------------------
        if self.publisher:
            try:
                await self.publisher.publish(response_envelope.model_dump())

                logger.info(
                    "handle.outbound.message.published",
                    extra={
                        "conversation_id": envelope.meta.conversation_id,
                    },
                )
            except Exception:
                logger.error("handle.outbound.publish.failed", exc_info=True)

    async def deliver(self, envelope: MessageEnvelope) -> None:
        """
        Entrega un envelope outbound ya procesado al WebSocket del cliente.
        Llamado desde /internal/outbound cuando el worker reenvía la respuesta
        al gateway para que la dispatche por WS.
        """
        if not self.ws_registry or not envelope.meta.conversation_id:
            return

        try:
            await self.ws_registry.send(
                conversation_id=envelope.meta.conversation_id,
                message={
                    "type": "chat.response",
                    "message": envelope.payload.get("message", ""),
                },
            )
            logger.info(
                "handle.outbound.ws.delivered",
                extra={"conversation_id": envelope.meta.conversation_id},
            )
        except Exception:
            logger.error("handle.outbound.ws.deliver.failed", exc_info=True)
