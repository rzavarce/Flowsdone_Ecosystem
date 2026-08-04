from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from ...domain.ports.outbound import ChannelConnectionRepositoryPort
from .ingest_message import IngestMessageUseCase

logger = logging.getLogger("usecase.route_channel_message")


class ChannelMessageNotRoutable(Exception):
    """No existe un channel_connection activo para (channel_type, external_id)."""


def build_conversation_id(project_id: UUID, channel_type: str, external_conversation_key: str) -> str:
    return f"{project_id}:{channel_type}:{external_conversation_key}"


class RouteChannelMessageUseCase:
    """
    Resuelve (channel_type, external_id) -> tenant/proyecto/agente vía
    ChannelConnectionRepositoryPort y delega en IngestMessageUseCase (ya
    existente, no se modifica), forzando transport="kafka" para todo mensaje
    de canal de chat, según la regla de enrutamiento del gateway: los canales
    de chat siempre van a Langflow vía Kafka.
    """

    def __init__(
        self,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        ingest_message_use_case: IngestMessageUseCase,
    ) -> None:
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
    ) -> None:
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
            transport="kafka",
            payload=payload,
            channel=channel_type,
            channel_connection_id=str(resolution.channel_connection_id),
            external_conversation_key=external_conversation_key,
        )
