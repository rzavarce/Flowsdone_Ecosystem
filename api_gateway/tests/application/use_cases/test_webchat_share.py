"""Tests for ManageWebchatShareLinksUseCase: public links to try an agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from app.application.use_cases.webchat_share import (
    InvalidShareDurationError,
    ManageWebchatShareLinksUseCase,
    hash_share_token,
)
from app.domain.models.agent import Agent
from api_gateway.tests.support.fakes import FakeWebchatShareLinkRepo

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)


class FakeAgents:
    def __init__(self, *agents: Agent) -> None:
        self.agents = {a.id: a for a in agents}

    async def get_by_id(self, agent_id):
        return self.agents.get(agent_id)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _agent(**over) -> Agent:
    fields = dict(id=uuid4(), project_id=uuid4(), name="Asistente de Flowsdone", langflow_flow_id="flow-1",
                  created_at=NOW, updated_at=NOW)
    fields.update(over)
    return Agent(**fields)


def _use_case(*agents: Agent, demo_url="https://chat.flowsdone.com/"):
    links, clock = FakeWebchatShareLinkRepo(), Clock()
    use_case = ManageWebchatShareLinksUseCase(links=links, agents=FakeAgents(*agents), demo_url=demo_url, clock=clock)
    return use_case, links, clock


def _token(url: str) -> str:
    return parse_qs(urlsplit(url).query)["share"][0]


async def test_a_link_without_expiry_is_the_default_and_opens_the_agent():
    agent = _agent()
    use_case, _, clock = _use_case(agent)
    by = uuid4()

    shared = await use_case.create(agent, created_by=by, expires_in_days=None)

    assert shared.link.expires_at is None and shared.link.created_by == by
    assert shared.url.startswith("https://chat.flowsdone.com/?share=")
    assert parse_qs(urlsplit(shared.url).query)["agent"] == ["Asistente de Flowsdone"]
    clock.now += timedelta(days=3650)
    opened = await use_case.open(_token(shared.url))
    assert opened.agent_id == agent.id and opened.workflow_id == "flow-1" and opened.share_id == shared.link.id


@pytest.mark.parametrize("days", [7, 30])
async def test_links_with_expiry_stop_working_after_it(days):
    agent = _agent()
    use_case, _, clock = _use_case(agent)
    shared = await use_case.create(agent, created_by=None, expires_in_days=days)
    token = _token(shared.url)

    assert shared.link.expires_at == NOW + timedelta(days=days)
    clock.now = NOW + timedelta(days=days) - timedelta(seconds=1)
    assert await use_case.open(token) is not None
    clock.now = NOW + timedelta(days=days)
    assert await use_case.open(token) is None
    assert await use_case.exists(token) is True


@pytest.mark.parametrize("days", [0, 1, 90, -7])
async def test_other_durations_are_refused(days):
    agent = _agent()
    use_case, links, _ = _use_case(agent)

    with pytest.raises(InvalidShareDurationError):
        await use_case.create(agent, created_by=None, expires_in_days=days)
    assert links.links == {}


async def test_tokens_are_random_and_only_their_hash_is_the_lookup_key():
    agent = _agent()
    use_case, links, _ = _use_case(agent)
    first = await use_case.create(agent, created_by=None, expires_in_days=None)
    second = await use_case.create(agent, created_by=None, expires_in_days=None)

    assert _token(first.url) != _token(second.url)
    assert len(_token(first.url)) >= 40
    assert set(links.links) == {hash_share_token(_token(first.url)), hash_share_token(_token(second.url))}


async def test_a_revoked_link_stops_working_but_is_still_recognised():
    agent = _agent()
    use_case, _, _ = _use_case(agent)
    shared = await use_case.create(agent, created_by=None, expires_in_days=None)
    token = _token(shared.url)

    assert await use_case.revoke(agent, shared.link.id) is True

    assert await use_case.open(token) is None
    assert await use_case.exists(token) is True
    assert await use_case.revoke(agent, shared.link.id) is False  # already revoked
    assert await use_case.list(agent) == []


async def test_a_link_of_another_agent_cannot_be_revoked_through_this_one():
    agent, other = _agent(), _agent(name="Otro")
    use_case, _, _ = _use_case(agent, other)
    shared = await use_case.create(other, created_by=None, expires_in_days=None)

    assert await use_case.revoke(agent, shared.link.id) is False
    assert await use_case.open(_token(shared.url)) is not None


async def test_the_link_follows_the_agents_current_flow():
    agent = _agent()
    agents = FakeAgents(agent)
    links = FakeWebchatShareLinkRepo()
    use_case = ManageWebchatShareLinksUseCase(links=links, agents=agents, demo_url="https://c/", clock=Clock())
    shared = await use_case.create(agent, created_by=None, expires_in_days=None)

    agents.agents[agent.id] = agent.model_copy(update={"langflow_flow_id": "flow-2"})

    assert (await use_case.open(_token(shared.url))).workflow_id == "flow-2"


@pytest.mark.parametrize("change", [{"status": "suspended"}, None])
async def test_a_suspended_or_deleted_agent_closes_its_links(change):
    agent = _agent()
    agents = FakeAgents(agent)
    use_case = ManageWebchatShareLinksUseCase(links=FakeWebchatShareLinkRepo(), agents=agents, demo_url="https://c/", clock=Clock())
    shared = await use_case.create(agent, created_by=None, expires_in_days=None)

    if change:
        agents.agents[agent.id] = agent.model_copy(update=change)
    else:
        del agents.agents[agent.id]

    assert await use_case.open(_token(shared.url)) is None


async def test_unknown_tokens_neither_open_nor_exist():
    use_case, _, _ = _use_case(_agent())

    assert await use_case.open("made-up") is None
    assert await use_case.exists("made-up") is False


async def test_list_returns_the_agents_links_newest_first_with_their_url():
    agent = _agent()
    use_case, _, clock = _use_case(agent)
    old = await use_case.create(agent, created_by=None, expires_in_days=7)
    clock.now += timedelta(minutes=1)
    new = await use_case.create(agent, created_by=None, expires_in_days=None)

    listed = await use_case.list(agent)

    assert {s.link.id for s in listed} == {old.link.id, new.link.id}
    assert all(s.url.startswith("https://chat.flowsdone.com/?share=") for s in listed)


async def test_the_url_keeps_existing_query_strings_in_the_demo_url():
    agent = _agent()
    use_case, _, _ = _use_case(agent, demo_url="https://x.test/demo?lang=es")

    shared = await use_case.create(agent, created_by=None, expires_in_days=None)

    assert shared.url.startswith("https://x.test/demo?lang=es&share=")
