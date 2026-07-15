from typing import Protocol
from app.domain.models.message import Message
from app.application.dto.message_dto import MessageDTO


class MessagePublisherPort(Protocol):
    async def publish(self, message: MessageDTO) -> None: ...


class LangflowExecutorPort(Protocol):
    async def run(
        self,
        *,
        workflow_id: str,
        payload: dict,
        conversation_id: str,
    ) -> dict: ...