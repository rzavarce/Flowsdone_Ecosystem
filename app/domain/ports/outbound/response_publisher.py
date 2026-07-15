from typing import Protocol, Literal
from pydantic import BaseModel
from uuid import UUID


class OutboundResponse(BaseModel):
    type: str = "chat.response"
    transport: Literal["kafka", "rabbitmq"]
    channel: str
    conversation_id: UUID
    workflow_id: UUID
    request_message_id: UUID
    correlation_id: str | None = None
    response: str


class ResponsePublisherPort(Protocol):
    async def publish(self, event: OutboundResponse) -> None: ...