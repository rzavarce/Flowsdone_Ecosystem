from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from app.core.config import settings
import logging

logger = logging.getLogger("kafka.admin")

REQUIRED_TOPICS = [
    NewTopic(
        name="inbound.messages",
        num_partitions=3,
        replication_factor=1,
    ),
    NewTopic(
        name="inbound.messages.dlq",
        num_partitions=3,
        replication_factor=1,
    ),
]


async def ensure_topics_exist() -> None:
    admin = AIOKafkaAdminClient(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS
    )

    await admin.start()
    try:
        existing = await admin.list_topics()
        to_create = [
            t for t in REQUIRED_TOPICS if t.name not in existing
        ]

        if to_create:
            logger.info(
                "creating.kafka.topics",
                extra={"topics": [t.name for t in to_create]},
            )
            await admin.create_topics(to_create)
        else:
            logger.info("kafka.topics.already.exist")

    finally:
        await admin.close()
