"""Use case behind "Try in web chat": a link to the generic demo page, bound
to one agent by a short-lived signed token (see application/services/webchat.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlencode

from app.application.services.webchat import TestTokenClaims, sign_test_token
from app.domain.models.agent import Agent


@dataclass(frozen=True)
class WebchatTestLink:
    """A demo link ready to open.

    Attributes:
        url (str): The demo page, with the token.
        expires_in (int): Seconds the token stays valid.
    """

    url: str
    expires_in: int


class IssueWebchatTestLinkUseCase:
    """Signs a test token for an agent and builds the demo link.

    Who may ask (staff with access to the agent's tenant) is checked by the
    caller; the token only lets that one agent be tried, for a while, and
    its conversations are not tracked nor billed.
    """

    def __init__(self, *, secret: str, ttl_seconds: int, demo_url: str) -> None:
        """Build the use case.

        Args:
            secret (str): Gateway secret the signing key derives from.
            ttl_seconds (int): Validity of each token.
            demo_url (str): The demo page's public URL.
        """
        self._secret = secret
        self._ttl = ttl_seconds
        self._demo_url = demo_url

    def execute(self, agent: Agent) -> WebchatTestLink:
        """Build the link for `agent`.

        Args:
            agent (Agent): The agent to try.

        Returns:
            WebchatTestLink: The demo link.
        """
        claims = TestTokenClaims(
            agent_id=str(agent.id), workflow_id=agent.langflow_flow_id, expires_at=int(time.time()) + self._ttl
        )
        query = urlencode({"test_token": sign_test_token(claims, self._secret), "agent": agent.name})
        separator = "&" if "?" in self._demo_url else "?"
        return WebchatTestLink(url=f"{self._demo_url}{separator}{query}", expires_in=self._ttl)
