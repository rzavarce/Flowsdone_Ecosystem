"""Implementations of ConversationEventPublisherPort."""

from __future__ import annotations

import logging

from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.ports.outbound import ConversationEventPublisherPort, MessagePublisherPort

logger = logging.getLogger("conversations.event_publisher")


class BrokerConversationEventPublisher(ConversationEventPublisherPort):
    """Publishes conversation events through a MessagePublisherPort bound
    to the conversation events topic (a KafkaPublisher in production).

    Events are keyed by conversation id, so all the messages of one
    conversation land on the same partition, in order.
    """

    def __init__(self, publisher: MessagePublisherPort) -> None:
        """Build the publisher.

        Args:
            publisher (MessagePublisherPort): Broker publisher already
                bound to the conversation events topic.
        """
        self._publisher = publisher

    async def publish_message_recorded(self, event: ConversationMessageRecorded) -> None:
        """Publish a recorded message.

        Args:
            event (ConversationMessageRecorded): The message event.
        """
        await self._publisher.publish(event.model_dump(mode="json"), key=str(event.conversation_id))


class NullConversationEventPublisher(ConversationEventPublisherPort):
    """Drops events - used when Kafka is disabled (ENABLE_KAFKA=false),
    so conversations are still tracked in Postgres but messages are not
    archived.
    """

    async def publish_message_recorded(self, event: ConversationMessageRecorded) -> None:
        """Log and discard a recorded message.

        Args:
            event (ConversationMessageRecorded): The message event.
        """
        logger.debug(
            "conversations.event.dropped",
            extra={"conversation_id": str(event.conversation_id), "message_id": str(event.message_id)},
        )
