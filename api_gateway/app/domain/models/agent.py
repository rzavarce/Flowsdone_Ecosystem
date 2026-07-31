from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class Agent(BaseModel):
    """
    Agente de Langflow configurado para un proyecto. `langflow_flow_id` es el
    workflow_id que se le pasa a IngestMessageUseCase/LangflowExecutor.
    """

    id: UUID
    project_id: UUID
    name: str
    langflow_flow_id: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    status: str = "active"
    created_at: datetime
    updated_at: datetime
