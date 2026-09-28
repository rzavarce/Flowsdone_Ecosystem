"""CreateChannelConnectionUseCase / UpdateChannelConnectionUseCase for the web chat."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.webchat import InvalidOriginError
from app.application.use_cases.create_channel_connection import CreateChannelConnectionUseCase, MissingExternalIdError
from app.application.use_cases.update_channel_connection import UpdateChannelConnectionUseCase
from api_gateway.tests.support.admin_world import InMemoryRepo
from api_gateway.tests.support.fakes import FakeSecretGenerator, make_channel_connection

pytestmark = pytest.mark.anyio


def _repo():
    return InMemoryRepo(lambda **f: make_channel_connection(**f), "project_id")


async def test_a_web_chat_gets_a_generated_public_key_and_normalized_origins():
    repo = _repo()
    use_case = CreateChannelConnectionUseCase(repo, FakeSecretGenerator("cd" * 32), {})

    channel = await use_case.execute(
        project_id=uuid4(), agent_id=uuid4(), channel_type="webchat", external_id="ignored",
        display_name="Chat web", credentials={}, config={"allowed_origins": ["Cliente.es/", "https://cliente.es"]},
    )

    assert channel.external_id == "wc_" + "cd" * 16
    assert channel.config["allowed_origins"] == ["https://cliente.es"]
    with pytest.raises(InvalidOriginError):
        await use_case.execute(project_id=uuid4(), agent_id=uuid4(), channel_type="webchat", external_id="",
                               display_name=None, credentials={}, config={"allowed_origins": ["mailto:x"]})


async def test_other_channels_still_need_their_external_id():
    use_case = CreateChannelConnectionUseCase(_repo(), FakeSecretGenerator(), {})
    with pytest.raises(MissingExternalIdError):
        await use_case.execute(project_id=uuid4(), agent_id=uuid4(), channel_type="instagram", external_id="",
                               display_name=None, credentials={}, config={})


async def test_updating_a_web_chat_normalizes_its_origins():
    repo = _repo()
    channel = await CreateChannelConnectionUseCase(repo, FakeSecretGenerator(), {}).execute(
        project_id=uuid4(), agent_id=uuid4(), channel_type="webchat", external_id="", display_name=None,
        credentials={}, config={},
    )
    update = UpdateChannelConnectionUseCase(repo, FakeSecretGenerator(), {})
    updated = await update.execute(channel.id, config={"allowed_origins": ["www.cliente.es"]})
    assert updated.config["allowed_origins"] == ["https://www.cliente.es"]
