"""Message DTO used when publishing to the legacy MessagePublisherPort."""

from uuid import uuid4

from pydantic import BaseModel, Field

from ...domain.models.message import Message


class MessageDTO(BaseModel):
    """Wire format for a message published to a broker.

    Attributes:
        version (int): DTO schema version.
        message_id (str): Unique identifier.
        conversation_id (str): Id of the conversation this message belongs to.
        channel (str): Channel the message was received on.
        sender_id (str): Id of the sender.
        payload (dict): Message payload.
        timestamp (str): ISO-formatted creation timestamp.
        correlation_id (str | None): Optional id for tracing a
            request/response pair.
        workflow_id (str): Id of the Langflow workflow to execute.
        retry_count (int): Number of delivery attempts so far.
    """

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
        """Build a MessageDTO from a domain Message.

        Args:
            message (Message): The domain message to convert.
            workflow_id (str): Id of the Langflow workflow to execute.
            correlation_id (str | None): Optional id for tracing a
                request/response pair.
            retry_count (int): Number of delivery attempts so far.

        Returns:
            MessageDTO: The equivalent DTO.
        """
        return cls(
            version=1,
            message_id=str(message.message_id),
            conversation_id=str(message.conversation_id),
            channel=message.channel.value,
            sender_id=message.sender_id,
            payload=message.payload,
            timestamp=message.timestamp.isoformat(),
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            retry_count=retry_count,
        )
