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
    """
    Canal conectado a un proyecto: credenciales y config necesarias para
    verificar/recibir webhooks de una plataforma concreta, y el agente de
    Langflow que debe atender los mensajes entrantes de ese canal.

    `credentials` viaja en texto plano dentro de la aplicación; el cifrado
    con Fernet es responsabilidad exclusiva del repositorio (adapters/outbound/db).
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
