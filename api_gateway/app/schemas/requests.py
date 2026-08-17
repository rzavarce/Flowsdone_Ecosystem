"""Generic webhook request schema.

Not currently referenced by any router; webhooks.py defines its own
GenericWebhookRequest instead. Kept for potential reuse.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class WebhookMessageRequest(BaseModel):
    """A generic inbound webhook message request.

    Attributes:
        workflow_id (UUID): Id of the Langflow flow that should run.
        conversation_id (UUID): Id of the conversation.
        sender_id (str): Id of the sender.
        payload (dict): Message payload.
        transport (Literal["kafka", "rabbitmq"]): Origin transport.
    """

    workflow_id: UUID
    conversation_id: UUID
    sender_id: str
    payload: dict
    transport: Literal["kafka", "rabbitmq"] = "kafka"
