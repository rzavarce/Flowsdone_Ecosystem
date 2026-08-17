"""Shared channel provider app credentials domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChannelAppProvider = Literal["meta", "twitter", "tiktok", "twilio"]


class ChannelApp(BaseModel):
    """Credentials of a provider's shared app.

    Meta covers Facebook and Instagram; there is a single app per
    provider for the whole SaaS, not per tenant. `channel_connections`
    is what varies per connected client/channel. For "twilio", this
    holds the SaaS-wide Account SID + Auth Token; the specific phone
    number lives in a channel_connections row with channel_type="voice".

    `credentials` travels in plain text within the application;
    encryption with Fernet is the exclusive responsibility of the
    repository (adapters/outbound/db).

    Attributes:
        id (UUID): Unique identifier.
        provider (ChannelAppProvider): Provider this app belongs to.
        credentials (Dict[str, Any]): App credentials (plain text
            in-process, encrypted at rest).
        config (Dict[str, Any]): Arbitrary app configuration.
        status (str): Lifecycle status (e.g. "active").
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    provider: ChannelAppProvider
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime
