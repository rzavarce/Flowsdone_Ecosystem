import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from ...domain.models.message_envelope import MessageEnvelope
from ...domain.ports.outbound import ChannelConnectionRepositoryPort, ChannelSenderPort

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
        channel_connection_repo: Optional[ChannelConnectionRepositoryPort] = None,
        channel_senders: Optional[Dict[str, ChannelSenderPort]] = None,
    ):
        self.publisher = publisher
        self.ws_registry = ws_registry
        self.channel_connection_repo = channel_connection_repo
        self.channel_senders = channel_senders or {}


    def _extract_text(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None

        if isinstance(value, dict):
            for key in ("message", "response", "output", "content", "text", "answer", "result"):
                if key in value:
                    extracted = self._extract_text(value[key])
                    if extracted:
                        return extracted

            for key in ("detail", "error"):
                if key in value:
                    extracted = self._extract_text(value[key])
                    if extracted:
                        return extracted

            for key in ("outputs", "data", "results"):
                if key in value:
                    extracted = self._extract_text(value[key])
                    if extracted:
                        return extracted

            return None

        if isinstance(value, list):
            for item in value:
                extracted = self._extract_text(item)
                if extracted:
                    return extracted

        return None

    async def execute(
        self,
        envelope: MessageEnvelope,
        result: Dict[str, Any],
    ) -> None:

        # ----------------------------------------------------------
        # 1. Extraer mensaje de Langflow
        # ----------------------------------------------------------
        response_message = self._extract_text(result)

        if not response_message:
            logger.error(
                "handle.outbound.invalid_langflow_response",
                extra={
                    "message_id": envelope.meta.message_id,
                    "result_preview": str(result)[:1000],
                },
            )
            response_message = "El workflow no devolvió una respuesta válida."

        # ----------------------------------------------------------
        # 2. Construir payload final
        # ----------------------------------------------------------
        response_payload = {
            "type": "chat.response",
            "response": response_message,
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
                await self.publisher.publish(
                    response_envelope.model_dump(), key=response_envelope.channel
                )

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
        Entrega un envelope outbound ya procesado. Llamado desde
        /internal/outbound cuando el worker (Kafka o RabbitMQ) reenvía la
        respuesta al gateway.

        - Si viene de webchat, la dispatcha por WebSocket (comportamiento
          original, sin cambios).
        - Si viene de un canal nativo (channel_connection_id presente),
          la envía de vuelta a ese canal con el sender correspondiente.
        """
        if self.ws_registry and envelope.meta.conversation_id:
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

        await self._deliver_to_channel(envelope)

    async def _deliver_to_channel(self, envelope: MessageEnvelope) -> None:
        channel_connection_id = envelope.meta.channel_connection_id
        if not channel_connection_id or not self.channel_connection_repo:
            return

        sender = self.channel_senders.get(envelope.channel or "")
        if not sender:
            return

        try:
            connection = await self.channel_connection_repo.get_by_id(
                UUID(channel_connection_id)
            )
            if not connection:
                logger.warning(
                    "handle.outbound.channel.connection_not_found",
                    extra={"channel_connection_id": channel_connection_id},
                )
                return

            await sender.send(
                external_id=connection.external_id,
                recipient_id=envelope.meta.external_conversation_key or "",
                text=envelope.payload.get("message", ""),
                credentials=connection.credentials,
            )

            logger.info(
                "handle.outbound.channel.delivered",
                extra={
                    "channel": envelope.channel,
                    "channel_connection_id": channel_connection_id,
                },
            )
        except Exception:
            logger.error("handle.outbound.channel.deliver.failed", exc_info=True)
