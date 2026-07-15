from uuid import uuid4
from pydantic import BaseModel, Field
from app.domain.models.message import Message

class MessageDTO(BaseModel):
    version: int = 1

    message_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    channel: str
    sender_id: str
    payload: dict
    timestamp: str
    correlation_id: str | None
    workflow_id: str
    retry_count: int = 0

    @classmethod
    def from_domain(
        cls,
        message: Message,
        *,
        workflow_id: str,
        correlation_id: str | None,
        retry_count: int = 0,
    ):
        return cls(
            version=1,
            message_id=str(message.message_id),  # o deja que default_factory lo genere
            conversation_id=str(message.conversation_id),
            channel=message.channel.value,
            sender_id=message.sender_id,
            payload=message.payload,
            timestamp=message.timestamp.isoformat(),
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            retry_count=retry_count,
        )