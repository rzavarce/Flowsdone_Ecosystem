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
    def __init__(self) -> None:
        self.calls = []

    async def run(self, *, workflow_id, payload, conversation_id):
        self.calls.append({"workflow_id": workflow_id, "conversation_id": conversation_id})
        return {"ok": True}


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
