"""Langflow HTTP executor: runs a flow and normalizes its response."""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.domain.ports.outbound import LangflowExecutorPort

logger = logging.getLogger("langflow.executor")


class LangflowExecutionError(Exception):
    """Raised when Langflow rejects a run or returns something that isn't
    a real result — an HTTP error status, or a 2xx response whose body
    isn't JSON (e.g. an unknown `workflow_id` falls through to Langflow's
    own frontend SPA, which answers 200 with its `index.html` instead of
    a 404 — see README.md section 15, "El pipeline completa... pero dice
    'El workflow no devolvió una respuesta válida'")."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# Langflow only builds the vertices required to produce the requested
# output_type. "chat" prunes any branch that doesn't feed the flow's Chat
# Output component, so a flow with a side-effect-only branch (e.g. an HTTP
# call fired after a conditional check, never wired back into Chat Output)
# would silently never execute that branch. "any" forces the full graph to
# build regardless of what feeds Chat Output.
_RUN_OUTPUT_TYPE = "any"
_RUN_INPUT_TYPE = "chat"


class LangflowExecutor(LangflowExecutorPort):
    """Calls the Langflow REST API to run a flow synchronously."""

    def __init__(self) -> None:
        headers = {}
        if settings.LANGFLOW_API_KEY:
            headers["x-api-key"] = settings.LANGFLOW_API_KEY

        self.client = httpx.AsyncClient(
            base_url=settings.LANGFLOW_BASE_URL,
            timeout=httpx.Timeout(60.0),
            headers=headers,
        )

    async def run(
        self,
        *,
        workflow_id: str,
        payload: dict[str, Any],
        conversation_id,
    ) -> dict | None:
        """Run a Langflow flow and return its parsed response.

        Args:
            workflow_id (str): Id of the Langflow flow to execute.
            payload (dict[str, Any]): Input payload; if it has a
                "message" key, that value is sent as-is, otherwise the
                whole payload is JSON-encoded as the input text.
            conversation_id: Id of the conversation, sent as the
                Langflow session_id for session continuity.

        Returns:
            dict | None: The parsed JSON response on success, or None
            if Langflow returned an empty (but successful) body.

        Raises:
            LangflowExecutionError: If Langflow answered with an HTTP
                error status, or with a 2xx status whose body isn't
                JSON — both are treated as a failed run, so
                `ExecuteWorkflowUseCase` marks the message failed and
                its offset is never committed (see that use case's own
                docstring), instead of silently recording the run as
                completed.
        """
        url = f"/api/v1/run/{workflow_id}"

        logger.info(
            "langflow.call.start",
            extra={
                "url": url,
                "payload": payload,
                "conversation_id": str(conversation_id),
            },
        )

        # Normalize the payload so UUIDs and other non-JSON-native
        # values become plain strings before being sent.
        safe_payload = json.loads(
            json.dumps(payload, default=str)
        )

        input_value = (
            safe_payload["message"]
            if "message" in safe_payload
            else json.dumps(safe_payload)
        )

        response = await self.client.post(
            url,
            json={
                "input_value": input_value,
                "output_type": _RUN_OUTPUT_TYPE,
                "input_type": _RUN_INPUT_TYPE,
                "session_id": str(conversation_id),
            },
        )

        if response.status_code >= 400:
            error_text = response.text
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    payload = response.json()
                    if isinstance(payload, dict):
                        if isinstance(payload.get("detail"), str):
                            error_text = payload["detail"]
                        elif isinstance(payload.get("detail"), dict):
                            error_text = payload["detail"].get("message") or payload["detail"].get("error") or response.text
                        elif payload.get("message"):
                            error_text = payload["message"]
            except Exception:
                error_text = response.text

            logger.error(
                "langflow.call.failed",
                extra={
                    "status_code": response.status_code,
                    "response_text": error_text,
                },
            )

            raise LangflowExecutionError(error_text, status_code=response.status_code)

        if not response.content:
            logger.info("langflow.call.success")
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            logger.info("langflow.call.success")
            return response.json()

        # A 2xx with a non-JSON body is not a real result — most often
        # Langflow's frontend SPA catch-all answering for a workflow_id
        # that doesn't exist (or isn't PUBLIC) with its index.html
        # instead of a 404. Treating this as success used to mark the
        # run completed and publish a bogus outbound message built from
        # HTML, silently and indefinitely, for a message that never
        # actually ran.
        logger.error(
            "langflow.call.non_json_response",
            extra={
                "status_code": response.status_code,
                "content_type": content_type,
                "response_preview": response.text[:500],
            },
        )
        raise LangflowExecutionError(
            f"Langflow returned a non-JSON 2xx response (content-type={content_type!r}); "
            "likely an unknown or non-PUBLIC workflow_id falling through to the frontend SPA.",
            status_code=response.status_code,
        )
