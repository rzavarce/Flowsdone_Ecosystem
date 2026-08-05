"""Channel connection domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

ChannelType = Literal[
    "facebook",
    "instagram",
    "twitter",
    "whatsapp_evolution",
    "telegram",
    "tiktok",
]


class ChannelConnection(BaseModel):
    """A channel connected to a project.

    Holds the credentials and configuration needed to verify/receive
    webhooks from a specific platform, and the Langflow agent that
    should answer inbound messages from that channel.

    `credentials` travels in plain text within the application;
    encryption with Fernet is the exclusive responsibility of the
    repository (adapters/outbound/db).

    Attributes:
        id (UUID): Unique identifier.
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent that answers messages on this channel.
        channel_type (ChannelType): Which platform this connection is for.
        external_id (str): Identifier used to route inbound webhooks
            (instance name, page id, bot token, etc., depending on the
            channel).
        display_name (Optional[str]): Optional human-readable label.
        credentials (Dict[str, Any]): Channel credentials (plain text
            in-process, encrypted at rest).
        config (Dict[str, Any]): Arbitrary channel configuration.
        status (str): Lifecycle status (e.g. "active").
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    project_id: UUID
    agent_id: UUID
    channel_type: ChannelType
    external_id: str
    display_name: Optional[str] = None
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime
