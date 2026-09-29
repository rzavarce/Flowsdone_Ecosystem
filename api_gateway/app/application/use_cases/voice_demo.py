"""Use case behind the demo page's "Call" tab: which number the browser
softphone dials, for whoever holds a valid demo link.

The softphone (Twilio Voice JS SDK) calls the agent's real voice channel,
through the same /webhooks/voice as a phone call, so the demo needs the
number of the voice channel connected to the link's agent. Only a valid
share link ("Share") or console test token ("Try in web chat") gets one:
the Twilio access token is what lets a browser place calls, and handing it
to anyone who finds the page would let them spend the account's minutes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.application.services.webchat import verify_test_token
from app.application.use_cases.webchat_share import ManageWebchatShareLinksUseCase
from app.domain.ports.outbound import AgentRepositoryPort, ChannelConnectionRepositoryPort

VOICE_CHANNEL = "voice"


@dataclass(frozen=True)
class VoiceDemoTarget:
    """Where the demo softphone calls.

    Attributes:
        agent_id (UUID): The agent that answers.
        to_number (str): Its voice channel's phone number (E.164).
    """

    agent_id: UUID
    to_number: str


class ResolveVoiceDemoTargetUseCase:
    """Finds the voice number of a demo link's agent."""

    def __init__(
        self,
        *,
        shares: ManageWebchatShareLinksUseCase,
        agents: AgentRepositoryPort,
        connections: ChannelConnectionRepositoryPort,
        secret: str,
    ) -> None:
        """Build the use case.

        Args:
            shares (ManageWebchatShareLinksUseCase): Opens share links.
            agents (AgentRepositoryPort): To find the agent's project.
            connections (ChannelConnectionRepositoryPort): To find its voice channel.
            secret (str): Gateway secret test tokens are signed with.
        """
        self._shares = shares
        self._agents = agents
        self._connections = connections
        self._secret = secret

    async def execute(self, *, share_token: Optional[str] = None, test_token: Optional[str] = None) -> Optional[VoiceDemoTarget]:
        """The number to call for a demo link.

        Args:
            share_token (Optional[str]): A share link's token.
            test_token (Optional[str]): A console test token.

        Returns:
            Optional[VoiceDemoTarget]: The target, or None if the link is not
            valid (anymore) or its agent has no active voice channel.
        """
        agent_id = await self._agent_id(share_token, test_token)
        if agent_id is None:
            return None
        agent = await self._agents.get_by_id(agent_id)
        if agent is None or agent.status != "active":
            return None
        for connection in await self._connections.list_by_project(agent.project_id):
            if (
                connection.channel_type == VOICE_CHANNEL
                and connection.agent_id == agent.id
                and connection.status == "active"
            ):
                return VoiceDemoTarget(agent_id=agent.id, to_number=connection.external_id)
        return None

    async def _agent_id(self, share_token: Optional[str], test_token: Optional[str]) -> Optional[UUID]:
        """The agent a link opens, if the link is valid.

        Args:
            share_token (Optional[str]): A share link's token.
            test_token (Optional[str]): A console test token.

        Returns:
            Optional[UUID]: The agent id, or None.
        """
        if share_token:
            shared = await self._shares.open(share_token)
            return shared.agent_id if shared else None
        if test_token:
            claims = verify_test_token(test_token, self._secret)
            if claims is None:
                return None
            try:
                return UUID(claims.agent_id)
            except ValueError:
                return None
        return None
