from typing import Literal

from pydantic import BaseModel
from uuid import UUID

class WebhookMessageRequest(BaseModel):
    workflow_id: UUID
    conversation_id: UUID
    sender_id: str
    payload: dict
    transport: Literal["kafka", "rabbitmq"] = "kafka"