from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum


class Channel(str, Enum):
    WEB = "web"
    WEBHOOK = "webhook"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class Message(BaseModel):
    message_id: UUID = uuid4()
    conversation_id: UUID
    channel: Channel
    sender_id: str
    payload: dict
    timestamp: datetime = datetime.utcnow()