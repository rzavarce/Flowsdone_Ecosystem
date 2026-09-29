"""Langflow account model: the Langflow user that stands for one tenant."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr


class LangflowAccount(BaseModel):
    """The Langflow user a tenant's agents live under.

    Langflow has no multi-tenancy of its own, but it does keep flows and
    projects per user. The gateway gives every tenant one Langflow user, so
    opening Langflow as that user shows only that tenant's agents.

    Attributes:
        tenant_id (UUID): The tenant this account belongs to.
        username (str): Langflow login name (derived from the tenant slug).
        password (SecretStr): Random password known only to the gateway; the
            browser never sees it (the SSO endpoint logs in server-side).
        langflow_user_id (Optional[str]): Id of the user inside Langflow, or
            None while the Langflow side has not been created yet.
        run_api_key (Optional[SecretStr]): The user's own Langflow API key,
            used to run the tenant's flows: Langflow resolves a flow's global
            variables for the key's owner. None until first needed.
        created_at (datetime): Creation timestamp.
    """

    tenant_id: UUID
    username: str
    password: SecretStr = Field(repr=False)
    langflow_user_id: Optional[str] = None
    run_api_key: Optional[SecretStr] = Field(default=None, repr=False)
    created_at: datetime
