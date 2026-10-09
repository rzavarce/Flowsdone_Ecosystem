"""Use case for creating a channel_connection end to end."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from app.application.services.webchat import normalize_origins
from app.domain.models.channel_connection import WEBCHAT, WEBCHAT_KEY_PREFIX, ChannelConnection
from app.domain.ports.outbound import (
    ChannelConnectionRepositoryPort,
    SecretGeneratorPort,
    WebhookRegistrarPort,
)
from app.application.services.webhook_registration import WebhookRegistrationError, register_or_compensate

__all__ = ["CreateChannelConnectionUseCase", "MissingExternalIdError", "WebhookRegistrationError"]


class MissingExternalIdError(ValueError):
    """A channel other than webchat was created without external_id (maps to 400)."""


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
                Ignored for webchat, whose public key is generated here.
            display_name (Optional[str]): Optional human-readable label.
            credentials (Dict[str, Any]): Channel credentials to
                encrypt and store. If the channel has a registrar and
                no value is set yet under its `secret_field`, one is
                generated automatically.
            config (Dict[str, Any]): Arbitrary channel configuration.

        Returns:
            ChannelConnection: The created channel connection.

        Raises:
            MissingExternalIdError: If a non-webchat channel has no external_id.
            InvalidOriginError: If a webchat allowed origin is not a website.
            WebhookRegistrationError: If the channel has a registrar
                and the external platform rejects the registration.
                The just-created channel_connection is deleted before
                this is raised.
        """
        if channel_type == WEBCHAT:
            # The web chat has no external platform: its routing key is a
            # public key the gateway generates (it goes in the widget
            # snippet), and its config carries the allowed websites.
            external_id = WEBCHAT_KEY_PREFIX + self._secret_generator.generate()[:32]
            config = {**config, "allowed_origins": normalize_origins(config.get("allowed_origins"))}
        elif not external_id:
            raise MissingExternalIdError(f"{channel_type} needs an external_id")

        registrar = self._webhook_registrars.get(channel_type)
        credentials = dict(credentials)

        if (
            registrar is not None
            and registrar.secret_field is not None
            and registrar.secret_field not in credentials
        ):
            credentials[registrar.secret_field] = self._secret_generator.generate()

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
            config=connection.config,
        )
        return connection
