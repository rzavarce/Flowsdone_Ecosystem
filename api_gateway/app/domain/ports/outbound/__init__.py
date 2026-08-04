from typing import Optional, Protocol
from ....application.dto.message_dto import MessageDTO

# ✅ re-export legacy ports (antes estaban en app/domain/ports/outbound.py)
class MessagePublisherPort(Protocol):
    async def publish(self, message: MessageDTO, *, key: Optional[str] = None) -> None: ...


class LangflowExecutorPort(Protocol):
    async def run(
        self,
        *,
        workflow_id: str,
        payload: dict,
        conversation_id: str,
    ) -> dict: ...


# ✅ export response publisher (si ya creaste response_publisher.py)
try:
    from .response_publisher import OutboundResponse, ResponsePublisherPort  # noqa: F401
except Exception:
    pass

# ✅ export admin/tenancy repository ports
from .admin_repositories import (  # noqa: F401
    AgentRepositoryPort,
    ChannelConnectionRepositoryPort,
    ProjectRepositoryPort,
    TenantRepositoryPort,
    WorkflowConfigRepositoryPort,
)
