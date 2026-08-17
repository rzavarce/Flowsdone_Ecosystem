"""RabbitMQ implementation of ResponsePublisherPort.

Not currently wired up anywhere in main.py or the workers; the active
outbound RabbitMQ path uses RabbitMQPublisher (rabbitmq_publisher.py)
instead. Kept for potential future use of the typed OutboundResponse
event.
"""

import aio_pika

from app.domain.ports.outbound.response_publisher import (
    OutboundResponse,
    ResponsePublisherPort,
)


class RabbitMQOutboundPublisher(ResponsePublisherPort):
    """Publishes OutboundResponse events to a RabbitMQ topic exchange."""

    def __init__(self, *, url: str, exchange_name: str = "outbound.messages"):
        """Build the publisher.

        Args:
            url (str): RabbitMQ connection URL.
            exchange_name (str): Topic exchange to declare and publish to.
        """
        self.url = url
        self.exchange_name = exchange_name
        self._conn = None
        self._channel = None
        self._exchange = None

    async def start(self) -> None:
        """Connect and declare the topic exchange."""
        self._conn = await aio_pika.connect_robust(self.url)
        self._channel = await self._conn.channel()
        self._exchange = await self._channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    async def stop(self) -> None:
        """Close the connection, if open."""
        if self._conn:
            await self._conn.close()

    async def publish(self, event: OutboundResponse) -> None:
        """Publish an outbound response event.

        Args:
            event (OutboundResponse): The event to publish. Routed
                using a "chat.response.{channel}" routing key so
                consumers can bind to specific channels.
        """
        routing_key = f"chat.response.{event.channel}"
        msg = aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
        )
        await self._exchange.publish(msg, routing_key=routing_key)
