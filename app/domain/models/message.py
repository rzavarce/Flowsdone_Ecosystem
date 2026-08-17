"""Canonical inbound message model (legacy, pre-MessageEnvelope shape)."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel


class Channel(str, Enum):
    """Supported inbound channels for the Message model."""

    WEB = "web"
    WEBHOOK = "webhook"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class Message(BaseModel):
    """A canonical inbound message.

    Attributes:
        message_id (UUID): Unique identifier.
        conversation_id (UUID): Id of the conversation this message
            belongs to.
        channel (Channel): Channel the message was received on.
        sender_id (str): Id of the sender.
        payload (dict): Message payload.
        timestamp (datetime): When the message was created.
    """

    message_id: UUID = uuid4()
    conversation_id: UUID
    channel: Channel
    sender_id: str
    payload: dict
    timestamp: datetime = datetime.utcnow()
