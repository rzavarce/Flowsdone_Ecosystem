"""CRM handoff: a conversation the bot hands over to a human agent working
in the client's own CRM / helpdesk.

While a handoff is open the bot stays silent: every message from the
contact is forwarded to the CRM, and the agent's replies come back
through Flowsdone (which still records the whole conversation). Closing
the ticket - or the contact's session expiring - gives the conversation
back to the bot.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Providers are added one by one (Zendesk, Salesforce, Jira Service
# Management, Zoho...); each is a CrmProviderPort adapter.
CrmProvider = Literal["generic_webhook"]

HandoffStatus = Literal["open", "closed", "expired"]
HandoffCloseReason = Literal["agent", "expired"]

# "integration.test" is only sent from the console, to check a setup.
CrmEventType = Literal["handoff.started", "message.inbound", "handoff.expired", "integration.test"]

# Name of the destination app (see AppConnectorPort) that a handed-off
# conversation is assigned to.
CRM_APP = "crm"


class CrmIntegration(BaseModel):
    """A project's connection to its CRM.

    `credentials` travels in plain text within the application;
    encryption is the exclusive responsibility of the repository.

    Attributes:
        id (UUID): Unique identifier.
        tenant_id (UUID): Owning tenant.
        project_id (UUID): Project whose conversations it receives (one
            integration per project).
        provider (CrmProvider): Which CRM adapter talks to it.
        config (Dict[str, Any]): Non-secret settings. For
            "generic_webhook": {"url": "https://..."}.
        credentials (Dict[str, Any]): Secrets. For "generic_webhook":
            "signing_secret" (we sign our events with it) and "api_key"
            (the CRM authenticates its replies with it), both generated
            by the gateway.
        status (str): "active" or "inactive".
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    tenant_id: UUID
    project_id: UUID
    provider: CrmProvider
    config: Dict[str, Any] = Field(default_factory=dict)
    credentials: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime


class Handoff(BaseModel):
    """One period during which a human in the CRM owns a conversation.

    Attributes:
        id (UUID): Unique identifier.
        session_id (str): Switchboard session (the conversation) handed over.
        tenant_id (UUID): Owning tenant.
        project_id (UUID): Owning project.
        integration_id (UUID): The CrmIntegration it went to.
        provider (CrmProvider): Provider of that integration, at the time.
        channel_type (str): Channel the contact writes on.
        contact (str): The contact's id on that channel.
        status (HandoffStatus): "open", "closed" (by the agent) or
            "expired" (the session ended first).
        reason (Optional[str]): Why the bot handed it over.
        external_ref (Optional[str]): The ticket/case id in the CRM, when
            the provider reports one.
        opened_at (datetime): When it was handed over.
        closed_at (Optional[datetime]): When it ended.
        close_reason (Optional[HandoffCloseReason]): How it ended.
    """

    id: UUID
    session_id: str
    tenant_id: UUID
    project_id: UUID
    integration_id: UUID
    provider: CrmProvider
    channel_type: str
    contact: str
    status: HandoffStatus = "open"
    reason: Optional[str] = None
    external_ref: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    close_reason: Optional[HandoffCloseReason] = None


class CrmEvent(BaseModel):
    """Something the CRM must learn about a handoff.

    Attributes:
        id (UUID): Unique event id; the CRM uses it to discard duplicates
            (deliveries are retried).
        type (CrmEventType): What happened.
        integration_id (UUID): Integration the event goes to.
        handoff_id (UUID): The handoff it belongs to.
        conversation_id (str): The conversation (session) id, which the CRM
            uses to reply or close.
        occurred_at (datetime): When it happened.
        data (Dict[str, Any]): Event-specific payload (contact, transcript,
            message text...).
    """

    id: UUID
    type: CrmEventType
    integration_id: UUID
    handoff_id: UUID
    conversation_id: str
    occurred_at: datetime
    data: Dict[str, Any] = Field(default_factory=dict)
