from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from ...domain.models.message_envelope import MessageEnvelope, MessageMeta

logger = logging.getLogger("usecase.ingest_message")


class IngestMessageUseCase:
    """
    Recibe un mensaje desde un canal de entrada (HTTP webhook, WS, etc.),
    lo normaliza al contrato canónico MessageEnvelope y lo publica en el broker.

    Este use case debe ser el punto único de construcción del envelope para
    entradas nuevas. Los consumers pueden ser tolerantes, pero los productores
    deben crear el formato completo y correcto.
    """

    def __init__(self, publisher_factory: Any):
        self.publisher_factory = publisher_factory

    async def execute(
        self,
        *,
        workflow_id: str,
        conversation_id: str,
        sender_id: Optional[str],
        transport: str,
        payload: Dict[str, Any],
        channel: Optional[str] = None,
        channel_connection_id: Optional[str] = None,
        external_conversation_key: Optional[str] = None,
    ) -> None:
        """
        Construye y publica un MessageEnvelope en dirección 'inbound'.

        Args:
            workflow_id: ID del flujo de Langflow que se debe ejecutar.
            conversation_id: ID de la conversación.
            sender_id: ID del emisor si aplica (cliente, usuario, bot, etc.).
            transport: transporte origen (rabbitmq, kafka, websocket, http, ...).
            payload: payload útil del mensaje (ej. {"message": "...", "callback_url": "..."}).
            channel: canal lógico si aplica (webchat, whatsapp, api, etc.).
            channel_connection_id: id del channel_connection que originó el
                mensaje, si viene de un canal nativo (no webchat). Necesario
                en el lado de salida para saber con qué credenciales responder.
            external_conversation_key: id del destinatario en la plataforma
                externa (remoteJid, psid, chat_id, ...), si aplica.
        """

        # -----------------------------------------------------------------
        # 1. Construcción del contrato canónico
        # -----------------------------------------------------------------
        envelope = MessageEnvelope(
            meta=MessageMeta(
                message_id=str(uuid4()),
                timestamp=datetime.utcnow(),
                direction="inbound",
                conversation_id=conversation_id,
                workflow_id=workflow_id,
                channel_connection_id=channel_connection_id,
                external_conversation_key=external_conversation_key,
            ),
            transport=transport,
            channel=channel or sender_id,
            payload=payload,
            response_to=None,
            version=1,
        )

        logger.info(
            "ingest.message.built",
            extra={
                "message_id": envelope.meta.message_id,
                "workflow_id": envelope.meta.workflow_id,
                "conversation_id": envelope.meta.conversation_id,
                "transport": envelope.transport,
                "channel": envelope.channel,
            },
        )

        # -----------------------------------------------------------------
        # 2. Resolución del publisher por transport
        # -----------------------------------------------------------------
        publisher = self.publisher_factory.create(transport)

        # -----------------------------------------------------------------
        # 3. Publicación en broker
        # -----------------------------------------------------------------
        # key=channel: en Kafka esto particiona los mensajes por canal, así
        # un canal lento/con picos no bloquea a los demás una vez que se
        # escalen réplicas de kafka_inbound_worker (RabbitMQ lo ignora).
        await publisher.publish(envelope.model_dump(), key=envelope.channel)

        logger.info(
            "ingest.message.published",
            extra={
                "message_id": envelope.meta.message_id,
                "workflow_id": envelope.meta.workflow_id,
                "conversation_id": envelope.meta.conversation_id,
            },
        )
