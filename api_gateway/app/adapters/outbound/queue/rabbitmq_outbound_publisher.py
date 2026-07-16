import aio_pika
from api_gateway.app.domain.ports.outbound.response_publisher import (
    ResponsePublisherPort,
    OutboundResponse,
)

class RabbitMQOutboundPublisher(ResponsePublisherPort):
    def __init__(self, *, url: str, exchange_name: str = "outbound.messages"):
        self.url = url
        self.exchange_name = exchange_name
        self._conn = None
        self._channel = None
        self._exchange = None

    async def start(self) -> None:
        self._conn = await aio_pika.connect_robust(self.url)
        self._channel = await self._conn.channel()
        self._exchange = await self._channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    async def stop(self) -> None:
        if self._conn:
            await self._conn.close()

    async def publish(self, event: OutboundResponse) -> None:
        routing_key = f"chat.response.{event.channel}"  # ✅ CLAVE
        msg = aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
        )
        await self._exchange.publish(msg, routing_key=routing_key)
