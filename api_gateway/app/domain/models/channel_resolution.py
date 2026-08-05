"""Channel resolution read model, used to route inbound channel messages."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel

from .channel_connection import ChannelType


class ChannelResolution(BaseModel):
    """Read-only DTO returned by
    ChannelConnectionRepositoryPort.get_by_channel_and_external_id().

    Resolves, in a single query, which tenant/project/agent an inbound
    channel message belongs to, with credentials already decrypted.

    Attributes:
        tenant_id (UUID): Id of the owning tenant.
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent that should answer.
        langflow_flow_id (str): Id of the Langflow flow the agent runs.
        channel_connection_id (UUID): Id of the matched channel connection.
        channel_type (ChannelType): Which platform this resolution is for.
        credentials (Dict[str, Any]): Decrypted channel credentials.
    """

    tenant_id: UUID
    project_id: UUID
    agent_id: UUID
    langflow_flow_id: str
    channel_connection_id: UUID
    channel_type: ChannelType
    credentials: Dict[str, Any]
