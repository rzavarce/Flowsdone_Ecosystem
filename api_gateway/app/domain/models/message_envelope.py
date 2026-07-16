from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageMeta(BaseModel):
    message_id: str
    timestamp: datetime
    direction: Optional[str] = None
    conversation_id: Optional[str] = None
    workflow_id: Optional[str] = None


class MessageEnvelope(BaseModel):
    meta: MessageMeta
    transport: Optional[str] = None
    channel: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    response_to: Optional[str] = None
    version: int = 1

    @classmethod
    def parse(cls, raw):
        from datetime import datetime

        try:
            # ---------------------------------------------
            # Decode input (Rabbit / Kafka / dict)
            # ---------------------------------------------
            if isinstance(raw, bytes):
                payload = json.loads(raw.decode("utf-8"))
            elif isinstance(raw, str):
                payload = json.loads(raw)
            elif isinstance(raw, dict):
                payload = raw
            else:
                raise TypeError(f"Unsupported type: {type(raw)}")

            # ---------------------------------------------
            # NORMALIZATION (backward compatibility)
            # ---------------------------------------------
            if "meta" not in payload:
                payload["meta"] = {}

            meta = payload["meta"]

            if "timestamp" not in meta:
                meta["timestamp"] = datetime.utcnow().isoformat()

            if "direction" not in meta:
                meta["direction"] = "inbound"

            # soporte legacy (`data`)
            if "payload" not in payload:
                payload["payload"] = payload.get("data", {}) or {}

            return cls.model_validate(payload)

        except Exception as e:
            raise ValueError(f"Parsing error: {e}") from e