"""Langflow HTTP executor: runs a flow and normalizes its response."""

import json
import logging
from typing import Any

import httpx

from ....core.config import settings
from ....domain.ports.outbound import LangflowExecutorPort

logger = logging.getLogger("langflow.executor")


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
            dict | None: The parsed JSON response on success, an error
            dict (`{"error": True, ...}`) on an HTTP error status, or
            None if Langflow returned an empty body.
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
                "output_type": "chat",
                "input_type": "chat",
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

            return {
                "error": True,
                "status_code": response.status_code,
                "message": error_text,
                "raw_response": response.text,
            }

        logger.info("langflow.call.success")

        if not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        return {"raw_response": response.text}
