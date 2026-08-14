"""RabbitMQ outbound worker: forwards outbound envelopes to the gateway's
/internal/outbound endpoint, HMAC-signed, so the process holding the
live WebSocket/channel state can deliver them.
"""

import asyncio
import json
import logging

import httpx

from api_gateway.app.adapters.inbound.queue.rabbitmq_consumer import RabbitMQConsumer
from api_gateway.app.application.services.hmac_signing import sign
from api_gateway.app.core.config import settings
from api_gateway.app.core.logging import setup_logging
from api_gateway.app.domain.models.message_envelope import MessageEnvelope

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("rabbitmq.outbound.worker")


async def main() -> None:
    """Wire up dependencies and consume the outbound queue until stopped.

    For each outbound message, forwards it to the gateway's
    /internal/outbound endpoint over HTTP, signed with an HMAC header.
    """
    logger.info(
        "rabbitmq.outbound.worker.starting",
        extra={
            "exchange": settings.RABBITMQ_OUTBOUND_EXCHANGE,
            "queue": settings.RABBITMQ_OUTBOUND_QUEUE,
            "routing_key": settings.RABBITMQ_OUTBOUND_ROUTING_KEY,
        },
    )

    gateway_url = settings.GATEWAY_INTERNAL_URL or "http://api:8000"
    endpoint = f"{gateway_url}/internal/outbound"

    client = httpx.AsyncClient(timeout=10)

    async def handler(body: bytes) -> None:
        """Forward one outbound message to /internal/outbound.

        Args:
            body (bytes): The raw message body.
        """
        try:
            envelope = MessageEnvelope.parse(body)
        except Exception:
            logger.error(
                "Invalid RabbitMQ message",
                extra={"body": body.decode("utf-8", errors="ignore")},
            )
            return

        if envelope.meta.direction != "outbound":
            return

        logger.info(
            "rabbitmq.outbound.message.received",
            extra={"conversation_id": str(envelope.meta.conversation_id)},
        )

        raw = json.loads(body.decode("utf-8"))
        signed_body = json.dumps(raw, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        sig = sign(signed_body, settings.CALLBACK_HMAC_SECRET)

        resp = await client.post(
            endpoint,
            content=signed_body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": sig,
            },
        )

        if resp.status_code >= 400:
            logger.error(
                "gateway.delivery.failed",
                extra={"status_code": resp.status_code, "body": resp.text},
            )
        else:
            logger.info(
                "gateway.delivery.ok",
                extra={"conversation_id": str(envelope.meta.conversation_id)},
            )

    consumer = RabbitMQConsumer(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_OUTBOUND_EXCHANGE,
        queue_name=settings.RABBITMQ_OUTBOUND_QUEUE,
        routing_key=settings.RABBITMQ_OUTBOUND_ROUTING_KEY,
    )

    await consumer.start(handler)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("rabbitmq.outbound.worker.stopped")
