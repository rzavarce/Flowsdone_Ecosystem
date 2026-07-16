import logging
from typing import Mapping

from ....domain.ports.outbound import MessagePublisherPort

logger = logging.getLogger("publisher.factory")


class PublisherFactory:
    """
    Factory responsible for selecting the correct outbound publisher
    based on the transport defined in the message envelope.
    """

    def __init__(self, publishers: Mapping[str, MessagePublisherPort]) -> None:
        self._publishers = {
            key.lower(): publisher for key, publisher in publishers.items()
        }

        logger.info(
            "publisher.factory.initialized",
            extra={"transports": list(self._publishers.keys())},
        )

    def create(self, transport: str) -> MessagePublisherPort:
        normalized = transport.lower()

        publisher = self._publishers.get(normalized)
        if not publisher:
            logger.error(
                "publisher.factory.transport_not_supported",
                extra={"transport": normalized},
            )
            raise ValueError(f"Unsupported transport: {transport}")

        logger.debug(
            "publisher.factory.publisher_selected",
            extra={"transport": normalized},
        )

        return publisher
