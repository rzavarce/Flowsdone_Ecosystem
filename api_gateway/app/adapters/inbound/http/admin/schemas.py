"""Pydantic request/response schemas for the admin HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from api_gateway.app.domain.models.channel_app import ChannelAppProvider
from api_gateway.app.domain.models.channel_connection import ChannelType


# Tenants

class TenantCreate(BaseModel):
    """Request body for POST /tenants.

    Attributes:
        name (str): Display name of the tenant.
        slug (str): Unique URL-safe identifier for the tenant.
    """

    name: str
    slug: str


class TenantUpdate(BaseModel):
    """Request body for PATCH /tenants/{tenant_id}. Unset fields are left unchanged.

    Attributes:
        name (Optional[str]): New display name.
        slug (Optional[str]): New URL-safe identifier.
        status (Optional[str]): New lifecycle status.
    """

    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None


class TenantOut(BaseModel):
    """Response body for tenant endpoints.

    Attributes:
        id (UUID): Unique identifier.
        name (str): Display name.
        slug (str): Unique URL-safe identifier.
        status (str): Lifecycle status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime


# Projects

class ProjectCreate(BaseModel):
    """Request body for POST /projects.

    Attributes:
        tenant_id (UUID): Id of the owning tenant.
        name (str): Display name of the project.
        slug (str): Unique URL-safe identifier for the project.
    """

    tenant_id: UUID
    name: str
    slug: str


class ProjectUpdate(BaseModel):
    """Request body for PATCH /projects/{project_id}. Unset fields are left unchanged.

    Attributes:
        name (Optional[str]): New display name.
        slug (Optional[str]): New URL-safe identifier.
        status (Optional[str]): New lifecycle status.
    """

    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    """Response body for project endpoints.

    Attributes:
        id (UUID): Unique identifier.
        tenant_id (UUID): Id of the owning tenant.
        name (str): Display name.
        slug (str): Unique URL-safe identifier.
        status (str): Lifecycle status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime


# Agents (Langflow)

class AgentCreate(BaseModel):
    """Request body for POST /agents.

    Attributes:
        project_id (UUID): Id of the owning project.
        name (str): Display name of the agent.
        langflow_flow_id (str): Id of the Langflow flow this agent runs.
        config (Dict[str, Any]): Arbitrary agent configuration.
        is_default (bool): Whether this is the project's default agent.
    """

    project_id: UUID
    name: str
    langflow_flow_id: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class AgentUpdate(BaseModel):
    """Request body for PATCH /agents/{agent_id}. Unset fields are left unchanged.

    Attributes:
        name (Optional[str]): New display name.
        langflow_flow_id (Optional[str]): New Langflow flow id.
        config (Optional[Dict[str, Any]]): New agent configuration.
        is_default (Optional[bool]): New default-agent flag.
        status (Optional[str]): New lifecycle status.
    """

    name: Optional[str] = None
    langflow_flow_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class AgentOut(BaseModel):
    """Response body for agent endpoints.

    Attributes:
        id (UUID): Unique identifier.
        project_id (UUID): Id of the owning project.
        name (str): Display name.
        langflow_flow_id (str): Id of the Langflow flow this agent runs.
        config (Dict[str, Any]): Arbitrary agent configuration.
        is_default (bool): Whether this is the project's default agent.
        status (str): Lifecycle status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    project_id: UUID
    name: str
    langflow_flow_id: str
    config: Dict[str, Any]
    is_default: bool
    status: str
    created_at: datetime
    updated_at: datetime


# Workflows (n8n)

class WorkflowConfigCreate(BaseModel):
    """Request body for POST /workflows.

    Attributes:
        project_id (UUID): Id of the owning project.
        name (str): Display name of the workflow configuration.
        n8n_workflow_id (str): Id of the n8n workflow it triggers.
        trigger_type (str): How the workflow is triggered.
        config (Dict[str, Any]): Arbitrary trigger configuration.
    """

    project_id: UUID
    name: str
    n8n_workflow_id: str
    trigger_type: str = "webhook"
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowConfigUpdate(BaseModel):
    """Request body for PATCH /workflows/{workflow_id}. Unset fields are left unchanged.

    Attributes:
        name (Optional[str]): New display name.
        n8n_workflow_id (Optional[str]): New n8n workflow id.
        trigger_type (Optional[str]): New trigger type.
        config (Optional[Dict[str, Any]]): New trigger configuration.
        status (Optional[str]): New lifecycle status.
    """

    name: Optional[str] = None
    n8n_workflow_id: Optional[str] = None
    trigger_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class WorkflowConfigOut(BaseModel):
    """Response body for workflow configuration endpoints.

    Attributes:
        id (UUID): Unique identifier.
        project_id (UUID): Id of the owning project.
        name (str): Display name.
        n8n_workflow_id (str): Id of the n8n workflow it triggers.
        trigger_type (str): How the workflow is triggered.
        config (Dict[str, Any]): Arbitrary trigger configuration.
        status (str): Lifecycle status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    project_id: UUID
    name: str
    n8n_workflow_id: str
    trigger_type: str
    config: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


# Channel connections

class ChannelConnectionCreate(BaseModel):
    """Request body for POST /channel-connections.

    Attributes:
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent that answers messages on this channel.
        channel_type (ChannelType): Which platform this connection is for.
        external_id (str): Identifier used to route inbound webhooks.
        display_name (Optional[str]): Optional human-readable label.
        credentials (Dict[str, Any]): Channel credentials to encrypt and store.
        config (Dict[str, Any]): Arbitrary channel configuration.
    """

    project_id: UUID
    agent_id: UUID
    channel_type: ChannelType
    external_id: str
    display_name: Optional[str] = None
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


class ChannelConnectionUpdate(BaseModel):
    """Request body for PATCH /channel-connections/{channel_connection_id}.
    Unset fields are left unchanged.

    Attributes:
        agent_id (Optional[UUID]): New answering agent.
        display_name (Optional[str]): New human-readable label.
        credentials (Optional[Dict[str, Any]]): New channel credentials.
        config (Optional[Dict[str, Any]]): New channel configuration.
        status (Optional[str]): New lifecycle status.
    """

    agent_id: Optional[UUID] = None
    display_name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ChannelConnectionOut(BaseModel):
    """Response body for channel connection endpoints.

    Never exposes `credentials` in plain text: only whether the channel
    has credentials loaded, so a GET cannot leak a client's tokens.

    Attributes:
        id (UUID): Unique identifier.
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent that answers messages on this channel.
        channel_type (ChannelType): Which platform this connection is for.
        external_id (str): Identifier used to route inbound webhooks.
        display_name (Optional[str]): Optional human-readable label.
        has_credentials (bool): Whether credentials are configured.
        config (Dict[str, Any]): Arbitrary channel configuration.
        status (str): Lifecycle status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    project_id: UUID
    agent_id: UUID
    channel_type: ChannelType
    external_id: str
    display_name: Optional[str] = None
    has_credentials: bool
    config: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


# Channel apps (shared per-provider app credentials)

class ChannelAppUpsert(BaseModel):
    """Request body for PUT /channel-apps/{provider}.

    Attributes:
        credentials (Dict[str, Any]): App credentials to encrypt and
            store. For "meta", `webhook_verify_token` is optional: if
            omitted, it is auto-generated (or the previously stored
            value is preserved on update) by UpsertChannelAppUseCase.
        config (Dict[str, Any]): Arbitrary app configuration.
    """

    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


class ChannelAppOut(BaseModel):
    """Response body for channel app endpoints.

    Never exposes `credentials` in plain text, same as ChannelConnectionOut.

    Attributes:
        id (UUID): Unique identifier.
        provider (ChannelAppProvider): Provider this app belongs to.
        has_credentials (bool): Whether credentials are configured.
        config (Dict[str, Any]): Arbitrary app configuration.
        status (str): Lifecycle status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    provider: ChannelAppProvider
    has_credentials: bool
    config: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class ChannelAppCredentialsOut(BaseModel):
    """Response body for GET /channel-apps/{provider}/credentials.

    Unlike ChannelAppOut, this exposes `credentials` in plain text -
    it exists solely so an admin can retrieve a value generated
    server-side (e.g. Meta's auto-generated `webhook_verify_token`)
    that they never typed in themselves and have no other way to read
    before pasting it into the provider's dashboard.

    Attributes:
        provider (ChannelAppProvider): Provider this app belongs to.
        credentials (Dict[str, Any]): App credentials in plain text.
    """

    provider: ChannelAppProvider
    credentials: Dict[str, Any]
