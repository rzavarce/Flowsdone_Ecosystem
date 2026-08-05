"""Use case for updating a channel_connection end to end."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from ...domain.models.channel_connection import ChannelConnection
from ...domain.ports.outbound import (
    ChannelConnectionRepositoryPort,
    SecretGeneratorPort,
    WebhookRegistrarPort,
)
from ..services.webhook_registration import WebhookRegistrationError, register_or_compensate

__all__ = ["UpdateChannelConnectionUseCase", "WebhookRegistrationError"]


class UpdateChannelConnectionUseCase:
    """Updates a channel_connection and, for channels with a webhook
    registrar, keeps the external platform in sync whenever
    `credentials` changes.

    `ChannelConnectionRepositoryPort.update` replaces `credentials`
    wholesale rather than merging it (see
    SqlAlchemyChannelConnectionRepository.update), so a PATCH that
    touches credentials without re-sending a channel's webhook secret
    would otherwise silently drop it — and, worse, a PATCH that *does*
    change the secret would leave the external platform still holding
    the old one, breaking the webhook until someone notices the 401s.
    This closes both gaps: the previous secret is preserved unless the
    caller explicitly overrides it, and any credentials change for a
    registrar-backed channel triggers a fresh registration.
    """

    def __init__(
        self,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        secret_generator: SecretGeneratorPort,
        webhook_registrars: Dict[str, WebhookRegistrarPort],
    ) -> None:
        """Build the use case.

        Args:
            channel_connection_repo (ChannelConnectionRepositoryPort):
                Repository used to read and persist the connection.
            secret_generator (SecretGeneratorPort): Generates a new
                webhook shared secret if a credentials update drops
                the existing one without supplying a replacement.
            webhook_registrars (Dict[str, WebhookRegistrarPort]): Maps
                channel_type to the registrar that keeps its webhook
                registration in sync with the external platform.
        """
        self._channel_connection_repo = channel_connection_repo
        self._secret_generator = secret_generator
        self._webhook_registrars = webhook_registrars

    async def execute(
        self,
        channel_connection_id: UUID,
        *,
        agent_id: Optional[UUID] = None,
        display_name: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[ChannelConnection]:
        """Update a channel_connection, re-registering its webhook if
        `credentials` changed and the channel supports it.

        Args:
            channel_connection_id (UUID): Id of the connection to update.
            agent_id (Optional[UUID]): New answering agent.
            display_name (Optional[str]): New human-readable label.
            credentials (Optional[Dict[str, Any]]): New credentials,
                replacing the stored ones wholesale. If the channel has
                a registrar and this omits its `secret_field`, the
                prior secret is preserved (or a new one generated if
                there wasn't one yet) rather than silently lost.
            config (Optional[Dict[str, Any]]): New channel configuration.
            status (Optional[str]): New lifecycle status.

        Returns:
            Optional[ChannelConnection]: The updated channel
            connection, or None if it does not exist.

        Raises:
            WebhookRegistrationError: If the channel has a registrar,
                `credentials` changed, and the external platform
                rejected the new registration. The connection's
                credentials are reverted to their pre-update value
                before this is raised.
        """
        existing = await self._channel_connection_repo.get_by_id(channel_connection_id)
        if existing is None:
            return None

        registrar = self._webhook_registrars.get(existing.channel_type)

        if credentials is not None and registrar is not None:
            credentials = dict(credentials)
            if registrar.secret_field is not None:
                credentials.setdefault(
                    registrar.secret_field,
                    existing.credentials.get(registrar.secret_field)
                    or self._secret_generator.generate(),
                )

        connection = await self._channel_connection_repo.update(
            channel_connection_id,
            agent_id=agent_id,
            display_name=display_name,
            credentials=credentials,
            config=config,
            status=status,
        )

        if registrar is None or credentials is None:
            return connection

        async def _restore_previous_credentials() -> None:
            await self._channel_connection_repo.update(
                channel_connection_id, credentials=existing.credentials
            )

        await register_or_compensate(
            registrar=registrar,
            external_id=existing.external_id,
            credentials=credentials,
            channel_type=existing.channel_type,
            on_failure=_restore_previous_credentials,
        )
        return connection
