"""Domain event for one message recorded in a conversation - what the
conversation archive (ClickHouse) stores, one row per event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.domain.models.session import MessageDirection

MessageSenderType = Literal["contact", "bot", "human"]

MESSAGE_RECORDED_EVENT = "conversation.message.recorded"


class ConversationMessageRecorded(BaseModel):
    """A message that was received from or sent to a contact.

    `message_id` is unique per event and is what makes archiving
    idempotent: a redelivered event lands on the same archive row.

    Attributes:
        event_type (str): Always MESSAGE_RECORDED_EVENT - lets the
            events topic carry other event types later.
        message_id (UUID): Unique id of this message/event.
        timestamp (datetime): When the message was received/sent.
        tenant_id (UUID): Id of the owning tenant.
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent handling the conversation.
        conversation_id (UUID): Id of the Conversation.
        session_id (str): Id of the Switchboard Session.
        channel_type (str): Channel the message went through.
        channel_connection_id (UUID): Id of the channel connection.
        direction (MessageDirection): "inbound" or "outbound".
        sender_type (MessageSenderType): Who wrote it: the contact, a
            bot (an app such as Langflow) or a human agent.
        app (str): Which app was handling the conversation.
        contact (str): Who is on the other end (phone number, username...).
        text (str): The message text.
        billable (bool): Whether an inbound message was handed to an app
            and so counts as platform usage (False when it was refused,
            e.g. by the plan's quota).
    """

    event_type: str = MESSAGE_RECORDED_EVENT
    message_id: UUID
    timestamp: datetime
    tenant_id: UUID
    project_id: UUID
    agent_id: UUID
    conversation_id: UUID
    session_id: str
    channel_type: str
    channel_connection_id: UUID
    direction: MessageDirection
    sender_type: MessageSenderType
    app: str
    contact: str
    text: str
    billable: bool = True
