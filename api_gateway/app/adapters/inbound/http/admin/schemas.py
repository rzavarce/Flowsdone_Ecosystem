from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .....domain.models.channel_connection import ChannelType


# ---------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------

class TenantCreate(BaseModel):
    name: str
    slug: str


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------

class ProjectCreate(BaseModel):
    tenant_id: UUID
    name: str
    slug: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------
# Agents (Langflow)
# ---------------------------------------------------------------------

class AgentCreate(BaseModel):
    project_id: UUID
    name: str
    langflow_flow_id: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    langflow_flow_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class AgentOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    langflow_flow_id: str
    config: Dict[str, Any]
    is_default: bool
    status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------
# Workflows (n8n)
# ---------------------------------------------------------------------

class WorkflowConfigCreate(BaseModel):
    project_id: UUID
    name: str
    n8n_workflow_id: str
    trigger_type: str = "webhook"
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowConfigUpdate(BaseModel):
    name: Optional[str] = None
    n8n_workflow_id: Optional[str] = None
    trigger_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class WorkflowConfigOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    n8n_workflow_id: str
    trigger_type: str
    config: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------
# Channel connections
# ---------------------------------------------------------------------

class ChannelConnectionCreate(BaseModel):
    project_id: UUID
    agent_id: UUID
    channel_type: ChannelType
    external_id: str
    display_name: Optional[str] = None
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


class ChannelConnectionUpdate(BaseModel):
    agent_id: Optional[UUID] = None
    display_name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ChannelConnectionOut(BaseModel):
    """
    Nunca expone `credentials` en claro: solo indica si el canal tiene
    credenciales cargadas, para no filtrar tokens de clientes por un GET.
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
