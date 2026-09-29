"""Use case behind the console's "Share" button: public links to try an agent.

"Try in web chat" gives staff a signed token that expires in minutes. A
share link is for someone outside (a prospect), may last 7 days, 30 days or
never expire, and therefore lives in the database so it can be revoked.
Anyone with the link can chat with the agent from the demo page, without
logging in; those conversations, like the console's tests, go straight to
the agent's flow and are neither tracked nor billed.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional
from urllib.parse import urlencode
from uuid import UUID

from app.domain.models.agent import Agent
from app.domain.models.webchat_share_link import WebchatShareLink
from app.domain.ports.outbound import AgentRepositoryPort, WebchatShareLinkRepositoryPort

# Validity a link can be created with, in days; None = never expires.
SHARE_LINK_DAYS = (7, 30, None)


class InvalidShareDurationError(ValueError):
    """The requested validity is not one of SHARE_LINK_DAYS (maps to 422)."""


def hash_share_token(token: str) -> str:
    """SHA-256 of a share token, the value links are looked up by.

    Args:
        token (str): The token from the URL.

    Returns:
        str: Its hex digest.
    """
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class SharedLink:
    """A share link as the console shows it.

    Attributes:
        link (WebchatShareLink): The stored link.
        url (str): The demo page URL that opens it.
    """

    link: WebchatShareLink
    url: str


@dataclass(frozen=True)
class SharedAgent:
    """What an opened share link routes to.

    Attributes:
        share_id (UUID): The link (rate-limit and conversation scope).
        agent_id (UUID): The agent.
        workflow_id (str): The agent's current Langflow flow.
        project_id (Optional[UUID]): The agent's project (where its demo
            conversations are recorded).
    """

    share_id: UUID
    agent_id: UUID
    workflow_id: str
    project_id: Optional[UUID] = None


class ManageWebchatShareLinksUseCase:
    """Create, list, revoke and open share links."""

    def __init__(
        self,
        *,
        links: WebchatShareLinkRepositoryPort,
        agents: AgentRepositoryPort,
        demo_url: str,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        """Build the use case.

        Args:
            links (WebchatShareLinkRepositoryPort): Share link storage.
            agents (AgentRepositoryPort): To find the agent a link opens.
            demo_url (str): The demo page's public URL (WEBCHAT_PUBLIC_URL).
            clock (Callable[[], datetime]): Current time (tests).
        """
        self._links = links
        self._agents = agents
        self._demo_url = demo_url
        self._clock = clock

    async def create(self, agent: Agent, *, created_by: Optional[UUID], expires_in_days: Optional[int]) -> SharedLink:
        """Create a link for `agent`.

        Args:
            agent (Agent): The agent to share.
            created_by (Optional[UUID]): Console user asking for it.
            expires_in_days (Optional[int]): 7, 30 or None (never expires).

        Returns:
            SharedLink: The link and its URL.

        Raises:
            InvalidShareDurationError: If the validity is not allowed.
        """
        if expires_in_days not in SHARE_LINK_DAYS:
            raise InvalidShareDurationError(f"expires_in_days must be one of {SHARE_LINK_DAYS}")
        token = secrets.token_urlsafe(32)
        expires_at = self._clock() + timedelta(days=expires_in_days) if expires_in_days else None
        link = await self._links.create(
            agent_id=agent.id,
            token=token,
            token_hash=hash_share_token(token),
            created_by=created_by,
            expires_at=expires_at,
        )
        return SharedLink(link=link, url=self._url(link, agent))

    async def list(self, agent: Agent) -> List[SharedLink]:
        """The agent's unrevoked links, newest first.

        Args:
            agent (Agent): The agent.

        Returns:
            List[SharedLink]: Its links (expired ones included, so they can be tidied up).
        """
        return [SharedLink(link=link, url=self._url(link, agent)) for link in await self._links.list_by_agent(agent.id)]

    async def revoke(self, agent: Agent, share_id: UUID) -> bool:
        """Revoke one of the agent's links: it stops working at once.

        Args:
            agent (Agent): The agent.
            share_id (UUID): The link.

        Returns:
            bool: False if the agent has no such link.
        """
        return await self._links.revoke(agent.id, share_id, self._clock())

    async def open(self, token: str) -> Optional[SharedAgent]:
        """Where a visitor's link leads, if it still works.

        Checked when the chat connects and again on every message, so
        revoking a link or suspending the agent cuts open chats too.

        Args:
            token (str): The token from the URL.

        Returns:
            Optional[SharedAgent]: The agent to chat with, or None if the
            link doesn't exist, expired, was revoked, or its agent is gone
            or suspended.
        """
        link = await self._links.get_by_token_hash(hash_share_token(token))
        if link is None or not link.is_usable(self._clock()):
            return None
        agent = await self._agents.get_by_id(link.agent_id)
        if agent is None or agent.status != "active":
            return None
        return SharedAgent(
            share_id=link.id, agent_id=agent.id, workflow_id=agent.langflow_flow_id, project_id=agent.project_id
        )

    async def exists(self, token: str) -> bool:
        """Whether a token belongs to a link at all (expired or revoked included).

        Lets the chat say "this link is no longer available" to someone who
        got a real link, while a made-up token is just refused.

        Args:
            token (str): The token from the URL.

        Returns:
            bool: True if some link has this token.
        """
        return await self._links.get_by_token_hash(hash_share_token(token)) is not None

    def _url(self, link: WebchatShareLink, agent: Agent) -> str:
        """The demo page URL that opens `link`.

        Args:
            link (WebchatShareLink): The link.
            agent (Agent): Its agent (its name titles the chat).

        Returns:
            str: The URL.
        """
        query = urlencode({"share": link.token.get_secret_value(), "agent": agent.name})
        separator = "&" if "?" in self._demo_url else "?"
        return f"{self._demo_url}{separator}{query}"
