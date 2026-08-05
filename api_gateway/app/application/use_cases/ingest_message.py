"""Use case for building and publishing the canonical inbound envelope."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from ...domain.models.message_envelope import MessageEnvelope, MessageMeta

logger = logging.getLogger("usecase.ingest_message")


class IngestMessageUseCase:
    """Receives a message from an inbound channel (HTTP webhook, WS,
    etc.), normalizes it into the canonical MessageEnvelope contract,
    and publishes it to the broker.

    This use case must be the single construction point for the
    envelope on new inbound messages. Consumers may be tolerant of
    older/partial shapes, but producers must always build the full,
    correct format.
    """

    def __init__(self, publisher_factory: Any):
        """Build the use case.

        Args:
            publisher_factory (Any): Factory used to select the
                publisher for a given transport.
        """
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
        """Build and publish a MessageEnvelope with direction "inbound".

        Args:
            workflow_id (str): Id of the Langflow flow that should run.
            conversation_id (str): Id of the conversation.
            sender_id (Optional[str]): Id of the sender, if applicable
                (client, user, bot).
            transport (str): Origin transport (rabbitmq, kafka,
                websocket, http, ...).
            payload (Dict[str, Any]): Message payload (e.g. {"message":
                "...", "callback_url": "..."}).
            channel (Optional[str]): Logical channel, if applicable
                (webchat, whatsapp, api, ...).
            channel_connection_id (Optional[str]): Id of the channel
                connection that originated the message, if it came from
                a native channel (not webchat). Required on the
                outbound side to know which credentials to answer with.
            external_conversation_key (Optional[str]): Id of the
                recipient on the external platform (remoteJid, psid,
                chat_id, ...), if applicable.
        """
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

        publisher = self.publisher_factory.create(transport)

        # key=channel: in Kafka this partitions messages by channel, so
        # a slow/bursty channel does not block the others once
        # kafka_inbound_worker replicas are scaled up (RabbitMQ ignores
        # this key).
        await publisher.publish(envelope.model_dump(), key=envelope.channel)

        logger.info(
            "ingest.message.published",
            extra={
                "message_id": envelope.meta.message_id,
                "workflow_id": envelope.meta.workflow_id,
                "conversation_id": envelope.meta.conversation_id,
            },
        )
