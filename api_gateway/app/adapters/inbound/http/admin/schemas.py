"""Pydantic request/response schemas for the admin HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.channel_app import ChannelAppProvider
from app.domain.models.channel_connection import ChannelType


# Tenants

class TenantCreate(BaseModel):
    """Request body for POST /tenants.

    A tenant always ships with its `client` user (see `CreateTenantUseCase`):
    created `pending`, activated by the same email flow as any other user -
    nobody, including the tenant's own client, gets a plaintext password.

    Attributes:
        name (str): Display name of the tenant.
        slug (str): Unique URL-safe identifier for the tenant.
        client_email (str): Login email for the tenant's `client` user.
        client_name (str): Display name for that user.
    """

    name: str
    slug: str
    client_email: str = Field(min_length=3, max_length=254)
    client_name: str = Field(min_length=1, max_length=200)


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


class TenantBillingUpdate(BaseModel):
    """Request body for `PUT /tenants/{tenant_id}/billing`. Every field is
    optional and `None` leaves it unchanged - pure data capture, filled in
    gradually as it becomes available.

    Attributes:
        legal_name (Optional[str]): Registered/legal company name.
        tax_id (Optional[str]): Tax identification number (RFC/NIF/VAT/EIN...).
        billing_email (Optional[str]): Where invoices/receipts are sent.
        billing_contact_name (Optional[str]): Person responsible for billing.
        billing_phone (Optional[str]): Contact phone for billing matters.
        address_line1 (Optional[str]): Street address.
        address_line2 (Optional[str]): Suite/floor/unit, if any.
        city (Optional[str]): City.
        state_province (Optional[str]): State/province/region.
        postal_code (Optional[str]): Postal/ZIP code.
        country (Optional[str]): Country.
        currency (Optional[str]): Billing currency (e.g. "USD", "MXN").
        plan (Optional[str]): Subscription tier, free text.
        billing_cycle (Optional[str]): e.g. "monthly", "annual"; free text.
        notes (Optional[str]): Anything else worth recording about billing.
    """

    legal_name: Optional[str] = Field(default=None, max_length=300)
    tax_id: Optional[str] = Field(default=None, max_length=100)
    billing_email: Optional[str] = Field(default=None, max_length=254)
    billing_contact_name: Optional[str] = Field(default=None, max_length=200)
    billing_phone: Optional[str] = Field(default=None, max_length=50)
    address_line1: Optional[str] = Field(default=None, max_length=300)
    address_line2: Optional[str] = Field(default=None, max_length=300)
    city: Optional[str] = Field(default=None, max_length=150)
    state_province: Optional[str] = Field(default=None, max_length=150)
    postal_code: Optional[str] = Field(default=None, max_length=30)
    country: Optional[str] = Field(default=None, max_length=100)
    currency: Optional[str] = Field(default=None, max_length=10)
    plan: Optional[str] = Field(default=None, max_length=100)
    billing_cycle: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=2000)


class TenantBillingOut(BaseModel):
    """Response body for the tenant billing profile endpoints (admin and self-service).

    Attributes: same as `TenantBillingUpdate`, plus:
        id (UUID): Unique identifier.
        tenant_id (UUID): The tenant this profile belongs to.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    tenant_id: UUID
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    billing_email: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    plan: Optional[str] = None
    billing_cycle: Optional[str] = None
    notes: Optional[str] = None
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


# ---------------------------------------------------------------------------
# Users (console accounts) — admin only
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Request body for creating a console user.

    No `password` field on purpose: nobody sets it for the new user anymore.
    They're created `pending` and emailed an activation link to set their
    own password (see `ProvisionUserUseCase`) - that's also what verifies
    the email actually belongs to them.

    Attributes:
        email (str): Login email (stored lowercase).
        name (str): Display name.
        role (str): `admin`, `tenant_manager`, `botmaster` or `client`.
        tenant_ids (List[UUID]): Tenants to assign; required unless `admin`.
        phone (Optional[str]): Optional contact phone.
        address (Optional[str]): Optional postal address.
        social_links (Optional[Dict[str, str]]): Optional links by network
            (`website`, `linkedin`, `x`, `facebook`, `instagram`).
    """

    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=200)
    role: str
    tenant_ids: List[UUID] = Field(default_factory=list)
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=300)
    social_links: Optional[Dict[str, str]] = None


class UserUpdate(BaseModel):
    """Request body for updating a user; every field is optional.

    Attributes:
        name (Optional[str]): New display name.
        role (Optional[str]): New role.
        status (Optional[str]): `active` or `disabled`.
        tenant_ids (Optional[List[UUID]]): New tenants (REPLACES the list).
        password (Optional[str]): New password; also closes the user's sessions.
        phone (Optional[str]): Optional phone; `""` clears it.
        address (Optional[str]): Optional address; `""` clears it.
        social_links (Optional[Dict[str, str]]): Replaces all the links.
    """

    name: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = None
    status: Optional[str] = None
    tenant_ids: Optional[List[UUID]] = None
    password: Optional[str] = Field(default=None, max_length=1024)
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=300)
    social_links: Optional[Dict[str, str]] = None


class UserOut(BaseModel):
    """Response schema for a user. Never includes the password hash.

    Attributes:
        id (UUID): Unique identifier.
        email (str): Login email.
        name (str): Display name.
        role (str): Access profile.
        status (str): `active` or `disabled`.
        tenant_ids (List[UUID]): Tenants the user belongs to (empty for admins).
        phone (Optional[str]): Optional contact phone.
        address (Optional[str]): Optional postal address.
        social_links (Dict[str, str]): Optional links by network.
        avatar_updated_at (Optional[datetime]): Set when the user has a photo
            (`GET /users/{id}/avatar`); doubles as a cache-buster.
        last_login_at (Optional[datetime]): Last successful sign-in.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    email: str
    name: str
    role: str
    status: str
    tenant_ids: List[UUID]
    phone: Optional[str] = None
    address: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)
    avatar_updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    """Body for `PATCH /me/profile`: what a user may change about themselves.

    Attributes:
        name (Optional[str]): New display name.
        phone (Optional[str]): Optional phone; `""` clears it.
        address (Optional[str]): Optional address; `""` clears it.
        social_links (Optional[Dict[str, str]]): Replaces all the links.
    """

    name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=300)
    social_links: Optional[Dict[str, str]] = None


class LangflowSessionCreate(BaseModel):
    """Body for opening the embedded Langflow as a tenant's user.

    Attributes:
        tenant_id (UUID): Tenant whose agents should be shown.
        project_id (Optional[UUID]): Project whose folder to land on; the
            tenant's first project when omitted.
    """

    tenant_id: UUID
    project_id: Optional[UUID] = None


class LangflowSessionOut(BaseModel):
    """URL the console loads in the iframe (a single-use ticket inside).

    Attributes:
        url (str): Gateway SSO URL; valid for a few seconds and only once.
    """

    url: str


class LangflowFlowOut(BaseModel):
    """A flow in a project's Langflow folder (GET /langflow/flows).

    Attributes:
        id (str): Langflow flow id.
        name (str): Flow name.
        description (Optional[str]): Flow description.
        agent_id (Optional[UUID]): The agent already registered for it in
            the project, if any.
    """

    id: str
    name: str
    description: Optional[str] = None
    agent_id: Optional[UUID] = None

