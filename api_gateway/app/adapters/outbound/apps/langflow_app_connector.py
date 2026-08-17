"""Langflow implementation of AppConnectorPort.

Confines the only Kafka-specific decision (which topic/transport a
turn goes through) to this adapter - Switchboard and AppConnectorPort
have zero vocabulary about transports, topics or Kafka, since future
connectors (Zendesk, email, ...) have nothing to do with any of that.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from api_gateway.app.domain.models.session import Session
from api_gateway.app.domain.ports.outbound import AppConnectorPort

logger = logging.getLogger("apps.langflow_connector")

_VOICE_CHANNEL_TYPE = "voice"
_VOICE_TRANSPORT = "kafka_voice"
_DEFAULT_TRANSPORT = "kafka"


class LangflowAppConnector(AppConnectorPort):
    """Dispatches a turn into the existing Kafka -> Langflow pipeline.

    Reuses IngestMessageUseCase exactly as RouteChannelMessageUseCase
    used to - no change to ExecuteWorkflowUseCase, the Kafka workers,
    or how the response eventually gets delivered
    (HandleOutboundResponseUseCase). This connector never answers
    synchronously: Langflow's response arrives later, asynchronously,
    through that unchanged pipeline.
    """

    app_name = "langflow"

    def __init__(self, ingest_message_use_case: Any) -> None:
        """Build the connector.

        Args:
            ingest_message_use_case (Any): The IngestMessageUseCase
                instance used to publish the turn to the broker.
        """
        self._ingest_message_use_case = ingest_message_use_case

    async def handle_turn(
        self,
        *,
        session: Session,
        message_text: str,
        raw_payload: Dict[str, Any],
    ) -> Optional[Any]:
        """Publish the turn to Langflow's Kafka pipeline.

        Args:
            session (Session): The conversation's current state; reads
                `session.variables["langflow_flow_id"]` (snapshotted by
                Switchboard when the session was created).
            message_text (str): The caller's message for this turn.
            raw_payload (Dict[str, Any]): The raw, channel-specific
                payload, forwarded as-is for debugging.

        Returns:
            None: Always - the response is delivered later by the
            existing kafka_inbound_worker/HandleOutboundResponseUseCase
            path, not by this call.
        """
        transport = _VOICE_TRANSPORT if session.channel_type == _VOICE_CHANNEL_TYPE else _DEFAULT_TRANSPORT

        await self._ingest_message_use_case.execute(
            workflow_id=session.variables["langflow_flow_id"],
            conversation_id=session.id,
            sender_id=session.user_identifier,
            transport=transport,
            payload={"message": message_text, "raw": raw_payload},
            channel=session.channel_type,
            channel_connection_id=str(session.channel_connection_id),
            external_conversation_key=session.external_conversation_key,
        )

        logger.info(
            "apps.langflow.turn.dispatched",
            extra={"session_id": session.id, "transport": transport},
        )

        return None
