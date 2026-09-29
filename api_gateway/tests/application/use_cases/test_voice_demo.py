"""Tests for ResolveVoiceDemoTargetUseCase: which number the demo softphone
calls, and only for a valid demo link."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from app.application.services.webchat import TestTokenClaims, sign_test_token
from app.application.use_cases.voice_demo import ResolveVoiceDemoTargetUseCase
from app.application.use_cases.webchat_share import ManageWebchatShareLinksUseCase
from app.domain.models.agent import Agent
from api_gateway.tests.support.fakes import FakeWebchatShareLinkRepo, make_channel_connection

pytestmark = pytest.mark.anyio

SECRET = "gateway-secret"


class FakeAgents:
    def __init__(self, *agents):
        self.agents = {a.id: a for a in agents}

    async def get_by_id(self, agent_id):
        return self.agents.get(agent_id)


class FakeConnections:
    def __init__(self, *connections):
        self.connections = list(connections)

    async def list_by_project(self, project_id=None):
        return [c for c in self.connections if project_id is None or c.project_id == project_id]


def _agent(**over):
    now = datetime.now(timezone.utc)
    fields = dict(id=uuid4(), project_id=uuid4(), name="Asistente", langflow_flow_id="flow-1", created_at=now, updated_at=now)
    fields.update(over)
    return Agent(**fields)


def _world(agent, *connections):
    agents = FakeAgents(agent)
    shares = ManageWebchatShareLinksUseCase(links=FakeWebchatShareLinkRepo(), agents=agents, demo_url="https://c/")
    use_case = ResolveVoiceDemoTargetUseCase(
        shares=shares, agents=agents, connections=FakeConnections(*connections), secret=SECRET
    )
    return use_case, shares, agents


def _voice(agent, **over):
    fields = dict(project_id=agent.project_id, agent_id=agent.id, channel_type="voice", external_id="+16014944500")
    fields.update(over)
    return make_channel_connection(**fields)


async def _share_token(shares, agent):
    shared = await shares.create(agent, created_by=None, expires_in_days=None)
    return parse_qs(urlsplit(shared.url).query)["share"][0]


def _test_token(agent, expires_in=600):
    claims = TestTokenClaims(agent_id=str(agent.id), workflow_id="flow-1", expires_at=int(time.time()) + expires_in)
    return sign_test_token(claims, SECRET)


async def test_a_share_link_dials_its_agents_voice_number():
    agent = _agent()
    use_case, shares, _ = _world(agent, _voice(agent), make_channel_connection(project_id=agent.project_id, agent_id=agent.id))

    target = await use_case.execute(share_token=await _share_token(shares, agent))

    assert target.agent_id == agent.id and target.to_number == "+16014944500"


async def test_a_console_test_token_also_gets_the_number():
    agent = _agent()
    use_case, _, _ = _world(agent, _voice(agent))

    assert (await use_case.execute(test_token=_test_token(agent))).to_number == "+16014944500"


async def test_invalid_or_expired_links_get_nothing():
    agent = _agent()
    use_case, shares, _ = _world(agent, _voice(agent))
    shared = await shares.create(agent, created_by=None, expires_in_days=None)
    await shares.revoke(agent, shared.link.id)

    assert await use_case.execute() is None
    assert await use_case.execute(share_token="made-up") is None
    assert await use_case.execute(share_token=parse_qs(urlsplit(shared.url).query)["share"][0]) is None
    assert await use_case.execute(test_token="forged.token") is None
    assert await use_case.execute(test_token=_test_token(agent, expires_in=-1)) is None


async def test_an_agent_without_an_active_voice_channel_has_no_call():
    agent, other = _agent(), _agent()
    use_case, shares, _ = _world(
        agent,
        _voice(agent, status="inactive"),
        _voice(other, project_id=agent.project_id, external_id="+34910000000"),
        make_channel_connection(project_id=agent.project_id, agent_id=agent.id, channel_type="telegram"),
    )

    assert await use_case.execute(share_token=await _share_token(shares, agent)) is None


async def test_a_suspended_agent_has_no_call():
    agent = _agent()
    use_case, _, agents = _world(agent, _voice(agent))
    agents.agents[agent.id] = agent.model_copy(update={"status": "suspended"})

    assert await use_case.execute(test_token=_test_token(agent)) is None
