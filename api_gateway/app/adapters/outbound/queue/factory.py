"""Factory that selects the right message publisher for a transport."""

import logging
from typing import Mapping

from app.domain.ports.outbound import MessagePublisherPort

logger = logging.getLogger("publisher.factory")


class PublisherFactory:
    """Selects the correct outbound publisher based on the transport
    defined in the message envelope.
    """

    def __init__(self, publishers: Mapping[str, MessagePublisherPort]) -> None:
        """Build the factory from the available publishers.

        Args:
            publishers (Mapping[str, MessagePublisherPort]): Mapping of
                transport name (e.g. "kafka", "rabbitmq") to its
                configured publisher.
        """
        self._publishers = {
            key.lower(): publisher for key, publisher in publishers.items()
        }

        logger.info(
            "publisher.factory.initialized",
            extra={"transports": list(self._publishers.keys())},
        )

    def create(self, transport: str) -> MessagePublisherPort:
        """Return the publisher configured for a transport.

        Args:
            transport (str): Transport name (case-insensitive).

        Returns:
            MessagePublisherPort: The matching publisher.

        Raises:
            ValueError: If no publisher is configured for the transport.
        """
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
