from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChannelAppProvider = Literal["meta", "twitter", "tiktok"]


class ChannelApp(BaseModel):
    """
    Credenciales de la App compartida de un proveedor (Meta cubre Facebook +
    Instagram; una sola App por proveedor para todo el SaaS — ver README
    sección 9). No es por tenant: `channel_connections` es lo que varía por
    cliente/canal conectado.

    `credentials` viaja en texto plano dentro de la aplicación; el cifrado
    con Fernet es responsabilidad exclusiva del repositorio (adapters/outbound/db).
    """

    id: UUID
    provider: ChannelAppProvider
    credentials: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime
