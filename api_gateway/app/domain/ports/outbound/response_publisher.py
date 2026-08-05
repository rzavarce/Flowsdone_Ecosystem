"""Outbound response event model and its publisher port."""

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel


class OutboundResponse(BaseModel):
    """A workflow response ready to be published to a broker.

    Attributes:
        type (str): Event type discriminator, always "chat.response".
        transport (Literal["kafka", "rabbitmq"]): Broker the event is
            published to.
        channel (str): Logical channel the response belongs to.
        conversation_id (UUID): Id of the conversation the response answers.
        workflow_id (UUID): Id of the workflow that produced the response.
        request_message_id (UUID): Id of the inbound message being answered.
        correlation_id (str | None): Optional id for tracing the
            request/response pair.
        response (str): The response text.
    """

    type: str = "chat.response"
    transport: Literal["kafka", "rabbitmq"]
    channel: str
    conversation_id: UUID
    workflow_id: UUID
    request_message_id: UUID
    correlation_id: str | None = None
    response: str


class ResponsePublisherPort(Protocol):
    """Contract for publishing an OutboundResponse event."""

    async def publish(self, event: OutboundResponse) -> None:
        """Publish an outbound response event.

        Args:
            event (OutboundResponse): The event to publish.
        """
        ...
