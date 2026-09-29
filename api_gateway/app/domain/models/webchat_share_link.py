"""Webchat share link: a public link to chat with one agent in the demo page."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr


class WebchatShareLink(BaseModel):
    """A link staff hand out so anyone (a prospect) can try an agent.

    Unlike the console's short-lived "try in web chat" token, a share link
    may never expire, so it lives in the database: that is what makes it
    revocable. It points at the agent, not at a flow, so it keeps working
    when the agent is moved to another flow.

    Attributes:
        id (UUID): Unique identifier.
        agent_id (UUID): The agent the link lets people chat with.
        token (SecretStr): The secret in the URL (stored encrypted; looked
            up by its hash).
        created_by (Optional[UUID]): Console user who created it (None for
            an API key).
        created_at (datetime): Creation timestamp.
        expires_at (Optional[datetime]): When it stops working; None = never.
        revoked_at (Optional[datetime]): When it was revoked; None = not revoked.
    """

    id: UUID
    agent_id: UUID
    token: SecretStr = Field(repr=False)
    created_by: Optional[UUID] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    def is_usable(self, now: datetime) -> bool:
        """Whether the link still opens the chat.

        Args:
            now (datetime): Current time (timezone-aware).

        Returns:
            bool: False once revoked or past its expiry.
        """
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > now
