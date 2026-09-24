"""Tests for DeleteProjectUseCase (project + its Langflow folder)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.delete_project import DeleteProjectUseCase
from app.domain.ports.outbound import LangflowSessionError
from api_gateway.tests.application.use_cases.test_langflow_sso import World

pytestmark = pytest.mark.anyio


def _setup():
    w = World()
    use_case = DeleteProjectUseCase(project_repo=w.projects, accounts=w.accounts, workspace=w.prepare, langflow=w.langflow)
    return w, use_case


async def test_deletes_the_langflow_folder_with_the_project():
    w, use_case = _setup()
    keep = await w.add_project("Ventas")
    gone = await w.add_project("Soporte")
    await w.prepare.open_workspace(w.tenant.id)
    folder = w.accounts.folders[gone.id]

    assert await use_case.execute(gone.id) is True

    assert folder not in w.langflow.folders
    assert w.accounts.folders[keep.id] in w.langflow.folders
    assert await w.projects.get_by_id(gone.id) is None


async def test_a_project_without_folder_is_deleted_without_touching_langflow():
    w, use_case = _setup()
    project = await w.add_project("Nunca abierto")

    assert await use_case.execute(project.id) is True
    assert w.langflow.calls == []


async def test_a_folder_deleted_by_hand_is_the_one_recreated_that_gets_deleted():
    w, use_case = _setup()
    project = await w.add_project("Soporte")
    await w.prepare.open_workspace(w.tenant.id)
    w.langflow.folders.clear()  # borrada a mano en el editor

    assert await use_case.execute(project.id) is True
    assert w.langflow.folders == {}


async def test_if_langflow_fails_the_project_is_kept():
    w, use_case = _setup()
    project = await w.add_project("Soporte")
    await w.prepare.open_workspace(w.tenant.id)

    async def boom(access_token, folder_id):
        raise LangflowSessionError("down")

    w.langflow.delete_project = boom
    with pytest.raises(LangflowSessionError):
        await use_case.execute(project.id)
    assert await w.projects.get_by_id(project.id) is not None


async def test_an_unknown_project_is_not_deleted():
    _, use_case = _setup()
    assert await use_case.execute(uuid4()) is False
