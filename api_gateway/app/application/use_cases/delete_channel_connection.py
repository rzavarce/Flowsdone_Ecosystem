"""Use case for deleting a channel_connection end to end."""

from __future__ import annotations

import logging
from typing import Dict
from uuid import UUID

from api_gateway.app.domain.ports.outbound import ChannelConnectionRepositoryPort, WebhookRegistrarPort

logger = logging.getLogger("usecase.delete_channel_connection")


class DeleteChannelConnectionUseCase:
    """Deletes a channel_connection and, best-effort, deregisters its
    webhook from the external platform.

    Deregistration failures (bot already removed by the client,
    platform API unreachable, ...) are logged but never block the
    deletion: the admin asked for this connection to be gone, and it
    shouldn't stay stuck in our system because an external API is
    flaky or the resource it points to is already gone on their side.
    """

    def __init__(
        self,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        webhook_registrars: Dict[str, WebhookRegistrarPort],
    ) -> None:
        """Build the use case.

        Args:
            channel_connection_repo (ChannelConnectionRepositoryPort):
                Repository used to read and delete the connection.
            webhook_registrars (Dict[str, WebhookRegistrarPort]): Maps
                channel_type to the registrar that can deregister its
                webhook. Channels absent from this map are just deleted.
        """
        self._channel_connection_repo = channel_connection_repo
        self._webhook_registrars = webhook_registrars

    async def execute(self, channel_connection_id: UUID) -> bool:
        """Deregister (best-effort) and delete a channel_connection.

        Args:
            channel_connection_id (UUID): Id of the connection to delete.

        Returns:
            bool: True if a connection was deleted, False if it did
            not exist.
        """
        connection = await self._channel_connection_repo.get_by_id(channel_connection_id)
        if connection is None:
            return False

        registrar = self._webhook_registrars.get(connection.channel_type)
        if registrar is not None:
            try:
                await registrar.deregister(
                    external_id=connection.external_id, credentials=connection.credentials
                )
            except Exception:
                logger.warning(
                    "delete_channel_connection.webhook_deregistration_failed",
                    extra={
                        "channel_type": connection.channel_type,
                        "channel_connection_id": str(channel_connection_id),
                    },
                    exc_info=True,
                )

        return await self._channel_connection_repo.delete(channel_connection_id)
