"""Use case for creating a channel_connection end to end."""

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

__all__ = ["CreateChannelConnectionUseCase", "WebhookRegistrationError"]


class CreateChannelConnectionUseCase:
    """Creates a channel_connection and, for channels that support it,
    auto-generates its webhook secret and registers the webhook with
    the external platform — so admins never have to hand-run curl
    (`setWebhook`, etc.) after calling the admin API.

    Orchestration only: secret generation, persistence, and platform
    registration are each delegated to their own port, kept swappable
    and independently testable (SRP/DIP). Adding a new auto-registered
    channel means adding an entry to WebhookRegistrarFactory, not
    touching this class (OCP).
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
                Repository used to persist the channel_connection.
            secret_generator (SecretGeneratorPort): Generates the
                webhook shared secret when a channel needs one and the
                caller did not already supply one.
            webhook_registrars (Dict[str, WebhookRegistrarPort]): Maps
                channel_type to the registrar that auto-registers its
                webhook with the external platform. Channels absent
                from this map keep the manual registration flow.
        """
        self._channel_connection_repo = channel_connection_repo
        self._secret_generator = secret_generator
        self._webhook_registrars = webhook_registrars

    async def execute(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        channel_type: str,
        external_id: str,
        display_name: Optional[str],
        credentials: Dict[str, Any],
        config: Dict[str, Any],
    ) -> ChannelConnection:
        """Create a channel_connection, auto-securing and
        auto-registering its webhook when the channel supports it.

        Args:
            project_id (UUID): Id of the owning project.
            agent_id (UUID): Id of the agent that answers messages on
                this channel.
            channel_type (str): Channel type (e.g. "telegram").
            external_id (str): Identifier used to route inbound
                webhooks (bot token, page id, instance name, ...).
            display_name (Optional[str]): Optional human-readable label.
            credentials (Dict[str, Any]): Channel credentials to
                encrypt and store. If the channel has a registrar and
                no value is set yet under its `secret_field`, one is
                generated automatically.
            config (Dict[str, Any]): Arbitrary channel configuration.

        Returns:
            ChannelConnection: The created channel connection.

        Raises:
            WebhookRegistrationError: If the channel has a registrar
                and the external platform rejects the registration.
                The just-created channel_connection is deleted before
                this is raised.
        """
        registrar = self._webhook_registrars.get(channel_type)
        credentials = dict(credentials)

        if registrar is not None and registrar.secret_field is not None:
            credentials.setdefault(registrar.secret_field, self._secret_generator.generate())

        connection = await self._channel_connection_repo.create(
            project_id=project_id,
            agent_id=agent_id,
            channel_type=channel_type,
            external_id=external_id,
            display_name=display_name,
            credentials=credentials,
            config=config,
        )

        if registrar is None:
            return connection

        async def _delete_orphaned_connection() -> None:
            await self._channel_connection_repo.delete(connection.id)

        await register_or_compensate(
            registrar=registrar,
            external_id=external_id,
            credentials=credentials,
            channel_type=channel_type,
            on_failure=_delete_orphaned_connection,
        )
        return connection
