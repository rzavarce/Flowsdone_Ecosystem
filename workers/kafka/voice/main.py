"""Voice worker: runs Langflow workflows for transcribed call turns and
delivers the response straight back to the gateway process, bypassing a
second Kafka hop.

Unlike the text pipeline (kafka_inbound_worker publishes to Kafka,
kafka_outbound_worker consumes it and forwards to /internal/outbound),
this is a single dedicated process: after running Langflow it posts
directly to /internal/outbound. Voice already gets its process-level
isolation from consuming a topic of its own (VOICE_KAFKA_TOPIC,
untouched by kafka_inbound_worker/kafka_outbound_worker); republishing
its own result back to Kafka just to immediately re-consume it would
add latency with no isolation benefit.
"""

import asyncio
import json
import logging

import asyncpg
import httpx

from api_gateway.app.adapters.inbound.queue.kafka_consumer import KafkaConsumer
from api_gateway.app.adapters.outbound.db.idempotency_repository import (
    PostgresIdempotencyRepository,
)
from api_gateway.app.adapters.outbound.langflow.executor import LangflowExecutor
from api_gateway.app.application.services.hmac_signing import sign
from api_gateway.app.application.services.langflow_result import extract_text_from_langflow_result
from api_gateway.app.application.use_cases.execute_workflow import ExecuteWorkflowUseCase
from api_gateway.app.core.config import settings
from api_gateway.app.core.logging import setup_logging
from api_gateway.app.domain.models.message_envelope import MessageEnvelope
from api_gateway.app.infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("kafka.voice.worker")

_FALLBACK_RESPONSE = "The workflow did not return a valid response."


async def main() -> None:
    """Wire up dependencies and consume VOICE_KAFKA_TOPIC until stopped.

    For each inbound call turn: runs its Langflow workflow
    (ExecuteWorkflowUseCase, idempotent via Postgres, the same
    repository text channels use), extracts the response text, and
    posts it straight to the gateway's /internal/outbound endpoint,
    HMAC-signed - the same generic endpoint text channels' outbound
    workers use, so delivery ends up at
    HandleOutboundResponseUseCase.deliver() -> TwilioVoiceSender
    without a voice-specific internal route.
    """
    logger.info(
        "kafka.voice.worker.starting",
        extra={
            "topic": settings.VOICE_KAFKA_TOPIC,
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        },
    )

    await ensure_topics_exist()

    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL_ASYNC,
        min_size=1,
        max_size=5,
    )

    idempotency_repo = PostgresIdempotencyRepository(pool)
    executor = LangflowExecutor()
    use_case = ExecuteWorkflowUseCase(idempotency_repo=idempotency_repo, executor=executor)

    gateway_url = settings.GATEWAY_INTERNAL_URL or "http://api:8000"
    endpoint = f"{gateway_url}/internal/outbound"
    client = httpx.AsyncClient(timeout=10)

    async def handler(body: dict) -> None:
        """Process one voice turn: run its workflow and deliver the response.

        Args:
            body (dict): The decoded message body.

        Raises:
            Exception: Re-raised if the body cannot be parsed as a
                MessageEnvelope, so the message is not committed.
        """
        try:
            envelope = MessageEnvelope.parse(body)
        except Exception:
            logger.error("kafka.voice.invalid_message", extra={"body": str(body)})
            raise

        if envelope.meta.direction != "inbound":
            return

        logger.info(
            "kafka.voice.turn.received",
            extra={
                "conversation_id": str(envelope.meta.conversation_id),
                "workflow_id": str(envelope.meta.workflow_id),
            },
        )

        result = await use_case.execute(envelope)
        if not result:
            return

        response_text = extract_text_from_langflow_result(result) or _FALLBACK_RESPONSE

        response_envelope = MessageEnvelope(
            meta=envelope.meta.model_copy(update={"direction": "outbound"}),
            transport=envelope.transport,
            channel=envelope.channel,
            payload={
                "type": "chat.response",
                "response": response_text,
                "message": response_text,
            },
            response_to=envelope.meta.message_id,
        )

        raw = response_envelope.model_dump()
        body_bytes = json.dumps(raw, separators=(",", ":"), sort_keys=True, default=str).encode(
            "utf-8"
        )
        signature = sign(body_bytes, settings.CALLBACK_HMAC_SECRET)

        resp = await client.post(
            endpoint,
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-Signature": signature},
        )

        if resp.status_code >= 400:
            logger.error(
                "kafka.voice.delivery.failed",
                extra={"status_code": resp.status_code, "body": resp.text},
            )
        else:
            logger.info(
                "kafka.voice.delivery.ok",
                extra={"conversation_id": str(envelope.meta.conversation_id)},
            )

    consumer = KafkaConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.VOICE_KAFKA_TOPIC,
        group_id="voice-workers",
    )

    await consumer.start(handler)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("kafka.voice.worker.stopped")
