"""Use case for routing a native channel message to its Langflow agent."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from ...domain.ports.outbound import ChannelConnectionRepositoryPort
from .ingest_message import IngestMessageUseCase

logger = logging.getLogger("usecase.route_channel_message")


class ChannelMessageNotRoutable(Exception):
    """Raised when no active channel_connection matches (channel_type, external_id)."""


def build_conversation_id(project_id: UUID, channel_type: str, external_conversation_key: str) -> str:
    """Build a deterministic conversation id for a channel message.

    Args:
        project_id (UUID): Id of the project the channel connection
            belongs to.
        channel_type (str): Channel type (e.g. "whatsapp_evolution",
            "telegram").
        external_conversation_key (str): Id of the sender on the
            external platform (remoteJid, psid, chat_id, ...).

    Returns:
        str: A conversation id of the form
        "{project_id}:{channel_type}:{external_conversation_key}".
    """
    return f"{project_id}:{channel_type}:{external_conversation_key}"


class RouteChannelMessageUseCase:
    """Resolves (channel_type, external_id) to a tenant/project/agent via
    ChannelConnectionRepositoryPort and delegates to IngestMessageUseCase,
    defaulting to transport="kafka" for every chat channel message, per
    the gateway's routing rule: chat channels always go to Langflow via
    a broker. Voice passes transport="kafka_voice" explicitly, so its
    turns land on a topic dedicated to voice instead of inbound.messages.
    """

    def __init__(
        self,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        ingest_message_use_case: IngestMessageUseCase,
    ) -> None:
        """Build the use case.

        Args:
            channel_connection_repo (ChannelConnectionRepositoryPort):
                Repository used to resolve inbound channel messages.
            ingest_message_use_case (IngestMessageUseCase): Use case
                that builds and publishes the canonical envelope.
        """
        self.channel_connection_repo = channel_connection_repo
        self.ingest_message_use_case = ingest_message_use_case

    async def execute(
        self,
        *,
        channel_type: str,
        external_id: str,
        external_conversation_key: str,
        sender_id: Optional[str],
        payload: Dict[str, Any],
        transport: str = "kafka",
    ) -> None:
        """Resolve a channel message and ingest it for Langflow processing.

        Args:
            channel_type (str): Channel type of the incoming message.
            external_id (str): External id carried by the webhook
                (instance name, page id, bot token, etc.).
            external_conversation_key (str): Id of the sender on the
                external platform (remoteJid, psid, chat_id, call_sid,
                ...).
            sender_id (Optional[str]): Id of the sender, if different
                from external_conversation_key.
            payload (Dict[str, Any]): Message payload to ingest.
            transport (str): Broker transport key to publish through,
                resolved via PublisherFactory (e.g. "kafka" for chat
                channels, "kafka_voice" for the voice channel's
                dedicated topic).

        Raises:
            ChannelMessageNotRoutable: If no active channel_connection
                matches (channel_type, external_id).
        """
        resolution = await self.channel_connection_repo.get_by_channel_and_external_id(
            channel_type, external_id
        )

        if resolution is None:
            logger.warning(
                "route.channel.not_found",
                extra={"channel_type": channel_type, "external_id": external_id},
            )
            raise ChannelMessageNotRoutable(
                f"no channel_connection for {channel_type}:{external_id}"
            )

        conversation_id = build_conversation_id(
            resolution.project_id, channel_type, external_conversation_key
        )

        logger.info(
            "route.channel.resolved",
            extra={
                "channel_type": channel_type,
                "project_id": str(resolution.project_id),
                "conversation_id": conversation_id,
            },
        )

        await self.ingest_message_use_case.execute(
            workflow_id=resolution.langflow_flow_id,
            conversation_id=conversation_id,
            sender_id=sender_id,
            transport=transport,
            payload=payload,
            channel=channel_type,
            channel_connection_id=str(resolution.channel_connection_id),
            external_conversation_key=external_conversation_key,
        )
