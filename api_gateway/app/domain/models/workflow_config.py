from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowConfig(BaseModel):
    """
    Automatización de n8n configurada para un proyecto. No interviene en el
    routing de mensajes de canal (esos van siempre a Langflow vía Kafka);
    se usa para disparar workflows de n8n vía RabbitMQ (/webhooks/generic).
    """

    id: UUID
    project_id: UUID
    name: str
    n8n_workflow_id: str
    trigger_type: str = "webhook"
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime
