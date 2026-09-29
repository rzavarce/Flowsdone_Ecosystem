"""Port for webchat share links (public links to try one agent)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol
from uuid import UUID

from app.domain.models.webchat_share_link import WebchatShareLink


class WebchatShareLinkRepositoryPort(Protocol):
    """Persistence of share links."""

    async def create(
        self,
        *,
        agent_id: UUID,
        token: str,
        token_hash: str,
        created_by: Optional[UUID],
        expires_at: Optional[datetime],
    ) -> WebchatShareLink:
        """Store a new link (token encrypted, looked up by its hash).

        Args:
            agent_id (UUID): The agent it opens.
            token (str): The secret in the URL.
            token_hash (str): SHA-256 of the token, used to find it.
            created_by (Optional[UUID]): Console user who created it.
            expires_at (Optional[datetime]): Expiry; None = never.

        Returns:
            WebchatShareLink: The stored link.
        """
        ...

    async def list_by_agent(self, agent_id: UUID) -> List[WebchatShareLink]:
        """Links of an agent that were not revoked, newest first.

        Args:
            agent_id (UUID): The agent.

        Returns:
            List[WebchatShareLink]: Its links (expired ones included).
        """
        ...

    async def get_by_token_hash(self, token_hash: str) -> Optional[WebchatShareLink]:
        """Find a link by the hash of its token.

        Args:
            token_hash (str): SHA-256 of the token.

        Returns:
            Optional[WebchatShareLink]: The link (revoked or not), or None.
        """
        ...

    async def revoke(self, agent_id: UUID, share_id: UUID, now: datetime) -> bool:
        """Revoke one of an agent's links.

        Args:
            agent_id (UUID): The agent (a link of another agent is not touched).
            share_id (UUID): The link.
            now (datetime): Revocation time.

        Returns:
            bool: False if the agent has no such (unrevoked) link.
        """
        ...
