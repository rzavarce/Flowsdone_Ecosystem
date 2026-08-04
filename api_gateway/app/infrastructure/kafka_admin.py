import logging

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.admin.new_partitions import NewPartitions

from ..core.config import settings

logger = logging.getLogger("kafka.admin")

REQUIRED_TOPICS = [
    (settings.KAFKA_TOPIC, settings.KAFKA_TOPIC_PARTITIONS),
    (settings.DLQ_TOPIC, settings.KAFKA_TOPIC_PARTITIONS),
]


async def ensure_topics_exist() -> None:
    """
    Crea los tópicos requeridos si no existen, y sube su cantidad de
    particiones si quedaron con menos de KAFKA_TOPIC_PARTITIONS (típicamente
    porque KAFKA_AUTO_CREATE_TOPICS_ENABLE los creó con 1 sola partición antes
    de que este admin corriera). Kafka no permite bajar particiones, solo
    subirlas — nunca se achica un tópico existente acá.
    """
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)

    await admin.start()
    try:
        existing_names = set(await admin.list_topics())

        to_create = [
            NewTopic(name=name, num_partitions=partitions, replication_factor=1)
            for name, partitions in REQUIRED_TOPICS
            if name not in existing_names
        ]

        if to_create:
            logger.info(
                "kafka.topics.creating",
                extra={"topics": [t.name for t in to_create]},
            )
            await admin.create_topics(to_create)

        already_present = [
            (name, partitions)
            for name, partitions in REQUIRED_TOPICS
            if name in existing_names
        ]

        to_expand: dict[str, NewPartitions] = {}
        if already_present:
            descriptions = await admin.describe_topics(
                [name for name, _ in already_present]
            )
            current_partitions = {
                d["topic"]: len(d["partitions"]) for d in descriptions
            }

            for name, desired in already_present:
                current = current_partitions.get(name, 0)
                if current and current < desired:
                    to_expand[name] = NewPartitions(total_count=desired)

        if to_expand:
            logger.info(
                "kafka.topics.expanding_partitions",
                extra={"topics": list(to_expand.keys())},
            )
            await admin.create_partitions(to_expand)

        if not to_create and not to_expand:
            logger.info("kafka.topics.already_up_to_date")

    finally:
        await admin.close()
