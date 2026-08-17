"""Agent domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class Agent(BaseModel):
    """A Langflow agent configured for a project.

    Attributes:
        id (UUID): Unique identifier.
        project_id (UUID): Id of the owning project.
        name (str): Display name.
        langflow_flow_id (str): The Langflow flow id passed to
            IngestMessageUseCase/LangflowExecutor to run this agent.
        config (Dict[str, Any]): Arbitrary agent configuration.
        is_default (bool): Whether this is the project's default agent.
        status (str): Lifecycle status (e.g. "active").
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
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
