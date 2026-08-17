"""Workflow configuration domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowConfig(BaseModel):
    """An n8n automation configured for a project.

    Does not participate in channel message routing (those always go
    to Langflow via Kafka); it is used to trigger n8n workflows via
    RabbitMQ (/webhooks/generic).

    Attributes:
        id (UUID): Unique identifier.
        project_id (UUID): Id of the owning project.
        name (str): Display name.
        n8n_workflow_id (str): Id of the n8n workflow this
            configuration triggers.
        trigger_type (str): How the workflow is triggered (e.g. "webhook").
        config (Dict[str, Any]): Arbitrary trigger configuration.
        status (str): Lifecycle status (e.g. "active").
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
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
