"""Kafka outbound worker: forwards outbound envelopes to the gateway's
/internal/outbound endpoint, HMAC-signed, so the process holding the
live WebSocket/channel state can deliver them.
"""

import asyncio
import json
import logging

import httpx

from api_gateway.app.adapters.inbound.queue.kafka_consumer import KafkaConsumer
from api_gateway.app.application.services.hmac_signing import sign
from api_gateway.app.core.config import settings
from api_gateway.app.core.logging import setup_logging
from api_gateway.app.domain.models.message_envelope import MessageEnvelope
from api_gateway.app.infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("kafka.outbound.worker")


async def main() -> None:
    """Wire up dependencies and consume KAFKA_TOPIC until stopped.

    For each outbound message, forwards it to the gateway's
    /internal/outbound endpoint over HTTP, signed with an HMAC header.
    """
    logger.info(
        "kafka.outbound.worker.starting",
        extra={"topic": settings.KAFKA_TOPIC, "group_id": "gateway-outbound"},
    )

    await ensure_topics_exist()

    gateway_url = getattr(settings, "GATEWAY_INTERNAL_URL", None) or "http://api:8000"
    endpoint = f"{gateway_url}/internal/outbound"

    client = httpx.AsyncClient(timeout=10)

    async def handler(raw: dict) -> None:
        """Forward one outbound message to /internal/outbound.

        Args:
            raw (dict): The decoded message body.
        """
        env = MessageEnvelope.model_validate(raw)
        if env.meta.direction != "outbound":
            return

        # Stable, UUID-safe serialization so the signature is deterministic.
        body = json.dumps(raw, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        sig = sign(body, settings.CALLBACK_HMAC_SECRET)

        resp = await client.post(
            endpoint,
            content=body,
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
                extra={"conversation_id": str(env.meta.conversation_id)},
            )

    consumer = KafkaConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        # Ideally a dedicated OUTBOUND_TOPIC once that gets split out.
        topic=settings.KAFKA_TOPIC,
        group_id="gateway-outbound",
    )

    await consumer.start(handler)


if __name__ == "__main__":
    asyncio.run(main())
