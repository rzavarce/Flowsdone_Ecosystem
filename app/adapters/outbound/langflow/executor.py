import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.domain.ports.outbound import LangflowExecutorPort

logger = logging.getLogger("langflow.executor")


class LangflowExecutor(LangflowExecutorPort):
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            base_url=settings.LANGFLOW_BASE_URL,
            timeout=httpx.Timeout(60.0),
        )

    async def run(
        self,
        *,
        workflow_id: str,
        payload: dict[str, Any],
        conversation_id,
    ) -> dict | None:
        url = f"/api/v1/run/{workflow_id}"

        logger.info(
            "langflow.call.start",
            extra={
                "url": url,
                "payload": payload,
                "conversation_id": str(conversation_id),
            },
        )

        # ✅ Normalizar payload (UUID → str)
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
            logger.error(
                "langflow.call.failed",
                extra={
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )

        response.raise_for_status()

        logger.info("langflow.call.success")

        if not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        return {"raw_response": response.text}
