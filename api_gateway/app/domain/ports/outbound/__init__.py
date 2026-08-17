"""Outbound port interfaces implemented by outbound adapters.

`MessagePublisherPort` and `LangflowExecutorPort` are defined here
directly (the sibling outbound.py module that used to hold them is
shadowed and unreachable, kept only for history). The remaining ports
are re-exported from their own files so callers can import everything
from `domain.ports.outbound`.
"""

from typing import Optional, Protocol

from ....application.dto.message_dto import MessageDTO


class MessagePublisherPort(Protocol):
    """Contract for publishing a message envelope to a message broker."""

    async def publish(self, message: MessageDTO, *, key: Optional[str] = None) -> None:
        """Publish a message.

        Args:
            message (MessageDTO): The message DTO to publish.
            key (Optional[str]): Optional partition/routing key (e.g. a
                Kafka partition key).
        """
        ...


class LangflowExecutorPort(Protocol):
    """Contract for executing a Langflow workflow."""

    async def run(
        self,
        *,
        workflow_id: str,
        payload: dict,
        conversation_id: str,
    ) -> dict:
        """Run a Langflow workflow.

        Args:
            workflow_id (str): Id of the Langflow flow to execute.
            payload (dict): Input payload for the flow.
            conversation_id (str): Id of the conversation, used for
                session continuity in Langflow.

        Returns:
            dict: The raw response returned by Langflow.
        """
        ...


try:
    from .response_publisher import OutboundResponse, ResponsePublisherPort  # noqa: F401
except Exception:
    pass

from .admin_repositories import (  # noqa: F401
    AgentRepositoryPort,
    ChannelAppRepositoryPort,
    ChannelConnectionRepositoryPort,
    ProjectRepositoryPort,
    TenantRepositoryPort,
    WorkflowConfigRepositoryPort,
)

from .app_connector import AppConnectorPort  # noqa: F401
from .call_session_repository import CallSessionRepositoryPort  # noqa: F401
from .channel_sender import ChannelSenderPort  # noqa: F401
from .secret_generator import SecretGeneratorPort  # noqa: F401
from .session_history_repository import SessionHistoryRepositoryPort  # noqa: F401
from .session_repository import SessionRepositoryPort  # noqa: F401
from .voice_provider import VoiceProviderPort  # noqa: F401
from .webhook_registrar import WebhookRegistrarPort  # noqa: F401
