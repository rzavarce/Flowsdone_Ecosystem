from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel

from .channel_connection import ChannelType


class ChannelResolution(BaseModel):
    """
    DTO de solo lectura devuelto por
    ChannelConnectionRepositoryPort.get_by_channel_and_external_id().

    Resuelve, en una sola consulta, a qué tenant/proyecto/agente pertenece
    un mensaje entrante de un canal, con las credenciales ya desencriptadas.
    """

    tenant_id: UUID
    project_id: UUID
    agent_id: UUID
    langflow_flow_id: str
    channel_connection_id: UUID
    channel_type: ChannelType
    credentials: Dict[str, Any]
