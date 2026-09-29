"""Tests for ExecuteWorkflowUseCase: which id Langflow gets as its
session_id, and idempotency."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.application.use_cases.execute_workflow import ExecuteWorkflowUseCase
from app.domain.models.message_envelope import MessageEnvelope, MessageMeta

pytestmark = pytest.mark.anyio


class _FakeExecutor:
    def __init__(self, refuse_keys=()) -> None:
        self.calls = []
        self.refuse_keys = set(refuse_keys)

    async def run(self, *, workflow_id, payload, conversation_id, api_key=None):
        self.calls.append({"workflow_id": workflow_id, "conversation_id": conversation_id, "api_key": api_key})
        if api_key in self.refuse_keys:
            raise _Refused(403)
        return {"ok": True}


class _Refused(Exception):
    """Like LangflowExecutionError: carries Langflow's status code."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class _FakeRunKeys:
    def __init__(self, key, replacement="sk-replaced"):
        self.key = key
        self.replacement = replacement
        self.replaced = []

    async def key_for(self, workflow_id):
        return self.key

    async def replace_key(self, workflow_id):
        self.replaced.append(workflow_id)
        return self.replacement


class _FakeIdempotency:
    def __init__(self, started: bool = True) -> None:
        self.started = started
        self.completed = []

    async def try_start(self, *, message_id, workflow_id):
        return self.started

    async def mark_completed(self, message_id):
        self.completed.append(message_id)

    async def mark_failed(self, message_id):
        pass


def _envelope(**meta) -> MessageEnvelope:
    return MessageEnvelope(
        meta=MessageMeta(
            message_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            conversation_id="proj:telegram:chat-1",
            workflow_id="flow-1",
            **meta,
        ),
        payload={"message": "hola"},
    )


async def test_langflow_session_is_the_conversation_when_llm_session_id_is_set():
    executor = _FakeExecutor()
    use_case = ExecuteWorkflowUseCase(executor=executor, idempotency_repo=_FakeIdempotency())

    await use_case.execute(_envelope(llm_session_id="conv-uuid"))

    assert executor.calls[0]["conversation_id"] == "conv-uuid"


async def test_langflow_session_falls_back_to_the_conversation_id():
    executor = _FakeExecutor()
    use_case = ExecuteWorkflowUseCase(executor=executor, idempotency_repo=_FakeIdempotency())

    await use_case.execute(_envelope())

    assert executor.calls[0]["conversation_id"] == "proj:telegram:chat-1"


async def test_duplicate_message_is_not_executed():
    executor = _FakeExecutor()
    use_case = ExecuteWorkflowUseCase(executor=executor, idempotency_repo=_FakeIdempotency(started=False))

    assert await use_case.execute(_envelope()) is None
    assert executor.calls == []


async def test_the_flow_runs_with_its_owner_tenants_key():
    executor = _FakeExecutor()
    use_case = ExecuteWorkflowUseCase(
        executor=executor, idempotency_repo=_FakeIdempotency(), run_keys=_FakeRunKeys("sk-tenant")
    )

    await use_case.execute(_envelope())

    assert executor.calls[0]["api_key"] == "sk-tenant"


async def test_without_run_keys_the_platform_key_is_used():
    executor = _FakeExecutor()
    use_case = ExecuteWorkflowUseCase(executor=executor, idempotency_repo=_FakeIdempotency())

    await use_case.execute(_envelope())

    assert executor.calls[0]["api_key"] is None


async def test_a_refused_tenant_key_is_replaced_and_the_run_retried_once():
    executor = _FakeExecutor(refuse_keys={"sk-deleted"})
    run_keys = _FakeRunKeys("sk-deleted")
    idempotency = _FakeIdempotency()
    use_case = ExecuteWorkflowUseCase(executor=executor, idempotency_repo=idempotency, run_keys=run_keys)

    assert await use_case.execute(_envelope()) == {"ok": True}
    assert [c["api_key"] for c in executor.calls] == ["sk-deleted", "sk-replaced"]
    assert run_keys.replaced == ["flow-1"]
    assert len(idempotency.completed) == 1


async def test_a_refused_replacement_key_is_not_retried_again():
    executor = _FakeExecutor(refuse_keys={"sk-deleted", "sk-replaced"})
    use_case = ExecuteWorkflowUseCase(
        executor=executor, idempotency_repo=_FakeIdempotency(), run_keys=_FakeRunKeys("sk-deleted")
    )

    with pytest.raises(_Refused):
        await use_case.execute(_envelope())
    assert len(executor.calls) == 2


async def test_a_refused_platform_key_is_not_retried():
    executor = _FakeExecutor(refuse_keys={None})
    run_keys = _FakeRunKeys(None)
    use_case = ExecuteWorkflowUseCase(executor=executor, idempotency_repo=_FakeIdempotency(), run_keys=run_keys)

    with pytest.raises(_Refused):
        await use_case.execute(_envelope())
    assert run_keys.replaced == []
