"""Outbound port interfaces implemented by outbound adapters.

`MessagePublisherPort` and `LangflowExecutorPort` are defined here
directly; the remaining ports are re-exported from their own files so
callers can import everything from `domain.ports.outbound`.
"""

from typing import Any, Optional, Protocol


class MessagePublisherPort(Protocol):
    """Contract for publishing an event to a message broker."""

    async def publish(self, event: Any, *, key: Optional[str] = None) -> None:
        """Publish an event.

        Args:
            event (Any): The event, JSON-serializable (e.g. a
                `MessageEnvelope.model_dump()`).
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
        api_key: Optional[str] = None,
    ) -> dict:
        """Run a Langflow workflow.

        Args:
            workflow_id (str): Id of the Langflow flow to execute.
            payload (dict): Input payload for the flow.
            conversation_id (str): Id of the conversation, used for
                session continuity in Langflow.
            api_key (Optional[str]): Langflow API key to run it with -
                the flow owner's, so its global variables resolve. None
                uses the platform's key.

        Returns:
            dict: The raw response returned by Langflow.
        """
        ...


try:
    from app.domain.ports.outbound.response_publisher import OutboundResponse, ResponsePublisherPort  # noqa: F401
except Exception:
    pass

from app.domain.ports.outbound.admin_repositories import (  # noqa: F401
    AgentRepositoryPort,
    AlreadyExistsError,
    ChannelAppRepositoryPort,
    ChannelConnectionRepositoryPort,
    ProjectRepositoryPort,
    TenantRepositoryPort,
    WorkflowConfigRepositoryPort,
)

from app.domain.ports.outbound.app_connector import AppConnectorPort  # noqa: F401
from app.domain.ports.outbound.auth import (  # noqa: F401
    AccountTokenStorePort,
    AuthSessionRepositoryPort,
    LoginThrottlePort,
    PasswordHasherPort,
    UserAlreadyExistsError,
    UserAvatarRepositoryPort,
    UserRepositoryPort,
)
from app.domain.ports.outbound.billing import (  # noqa: F401
    PlanInUseError,
    PlanRepositoryPort,
    QuotaCounterPort,
    StatementRepositoryPort,
    SubscriptionRepositoryPort,
)
from app.domain.ports.outbound.call_session_repository import CallSessionRepositoryPort  # noqa: F401
from app.domain.ports.outbound.channel_sender import ChannelSenderPort  # noqa: F401
from app.domain.ports.outbound.conversations import (  # noqa: F401
    ConversationEventPublisherPort,
    ConversationRepositoryPort,
    MessageArchivePort,
)
from app.domain.ports.outbound.analytics import AnalyticsUnavailableError, DashboardEmbedPort  # noqa: F401
from app.domain.ports.outbound.email import EmailSendError, EmailSenderPort  # noqa: F401
from app.domain.ports.outbound.langflow_sso import (  # noqa: F401
    LangflowAccountRepositoryPort,
    LangflowAdminPort,
    LangflowFlowSummary,
    LangflowSessionError,
    LangflowTokens,
    SsoTicketStorePort,
)
from app.domain.ports.outbound.secret_generator import SecretGeneratorPort  # noqa: F401
from app.domain.ports.outbound.session_history_repository import SessionHistoryRepositoryPort  # noqa: F401
from app.domain.ports.outbound.session_repository import SessionRepositoryPort  # noqa: F401
from app.domain.ports.outbound.tenant_billing_profile import TenantBillingProfileRepositoryPort  # noqa: F401
from app.domain.ports.outbound.usage import (  # noqa: F401
    CostRateRepositoryPort,
    LlmGeneration,
    LlmUsageSourcePort,
    SyncCursorRepositoryPort,
    UsageStorePort,
)
from app.domain.ports.outbound.voice_provider import VoiceProviderPort  # noqa: F401
from app.domain.ports.outbound.contacts import ContactKey, ContactRepositoryPort, SenderProfileLookupPort  # noqa: F401
from app.domain.ports.outbound.webchat_share import WebchatShareLinkRepositoryPort  # noqa: F401
from app.domain.ports.outbound.webhook_registrar import WebhookRegistrarPort  # noqa: F401
from app.domain.ports.outbound.callbacks import CallbackSenderPort  # noqa: F401
from app.domain.ports.outbound.connections import JsonConnection  # noqa: F401
