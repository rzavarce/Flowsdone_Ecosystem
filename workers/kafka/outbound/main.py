import asyncio
import json
import hmac
import hashlib
import logging

import httpx

from api_gateway.app.core.config import settings
from api_gateway.app.core.logging import setup_logging
from api_gateway.app.adapters.inbound.queue.kafka_consumer import KafkaConsumer
from api_gateway.app.domain.models.message_envelope import MessageEnvelope
from api_gateway.app.infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("kafka.outbound.worker")


def sign(body: bytes) -> str:
    return hmac.new(
        settings.CALLBACK_HMAC_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


async def main() -> None:
    logger.info(
        "kafka.outbound.worker.starting",
        extra={"topic": settings.KAFKA_TOPIC, "group_id": "gateway-outbound"},
    )

    await ensure_topics_exist()

    gateway_url = getattr(settings, "GATEWAY_INTERNAL_URL", None) or "http://api:8000"
    endpoint = f"{gateway_url}/internal/outbound"

    client = httpx.AsyncClient(timeout=10)

    async def handler(raw: dict) -> None:
        env = MessageEnvelope.model_validate(raw)
        if env.meta.direction != "outbound":
            return

        # Serialización estable + UUID safe
        body = json.dumps(raw, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        sig = sign(body)

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
        topic=settings.KAFKA_TOPIC,  # ideal: OUTBOUND_TOPIC cuando lo separes
        group_id="gateway-outbound",
    )

    await consumer.start(handler)


if __name__ == "__main__":
    asyncio.run(main())