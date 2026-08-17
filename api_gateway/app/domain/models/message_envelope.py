"""Canonical message envelope exchanged over Kafka/RabbitMQ."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageMeta(BaseModel):
    """Metadata carried by every MessageEnvelope.

    Attributes:
        message_id (str): Unique id of this message.
        timestamp (datetime): When the message was created.
        direction (Optional[str]): "inbound" or "outbound".
        conversation_id (Optional[str]): Id of the conversation this
            message belongs to.
        workflow_id (Optional[str]): Id of the Langflow workflow to
            execute (inbound) or that produced the response (outbound).
        channel_connection_id (Optional[str]): Id of the channel
            connection that originated the message, if it came from a
            native channel (None for webchat).
        external_conversation_key (Optional[str]): Id of the recipient
            on the external platform (remoteJid, psid, chat_id, etc.),
            if applicable.
    """

    message_id: str
    timestamp: datetime
    direction: Optional[str] = None
    conversation_id: Optional[str] = None
    workflow_id: Optional[str] = None
    channel_connection_id: Optional[str] = None
    external_conversation_key: Optional[str] = None


class MessageEnvelope(BaseModel):
    """The canonical message contract used across all transports.

    Attributes:
        meta (MessageMeta): Message metadata.
        transport (Optional[str]): Origin/destination transport (e.g.
            "kafka", "rabbitmq").
        channel (Optional[str]): Logical channel (e.g. "webchat",
            "whatsapp_evolution").
        payload (Dict[str, Any]): Transport-specific message payload.
        response_to (Optional[str]): Id of the message this one
            responds to, if any.
        version (int): Envelope schema version.
    """

    meta: MessageMeta
    transport: Optional[str] = None
    channel: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    response_to: Optional[str] = None
    version: int = 1

    @classmethod
    def parse(cls, raw):
        """Parse a raw broker message into a MessageEnvelope.

        Accepts bytes, a JSON string, or an already-decoded dict, and
        fills in defaults for fields older producers may not have set
        (timestamp, direction, and the legacy `data` payload key), so
        older messages remain readable by current consumers.

        Args:
            raw (bytes | str | dict): The raw message as received from
                Kafka/RabbitMQ, or an equivalent dict.

        Returns:
            MessageEnvelope: The parsed envelope.

        Raises:
            ValueError: If `raw` is not bytes/str/dict, or does not
                match the envelope schema.
        """
        from datetime import datetime

        try:
            # Decode input (RabbitMQ / Kafka / dict).
            if isinstance(raw, bytes):
                payload = json.loads(raw.decode("utf-8"))
            elif isinstance(raw, str):
                payload = json.loads(raw)
            elif isinstance(raw, dict):
                payload = raw
            else:
                raise TypeError(f"Unsupported type: {type(raw)}")

            # Backward-compatible normalization for older producers.
            if "meta" not in payload:
                payload["meta"] = {}

            meta = payload["meta"]

            if "timestamp" not in meta:
                meta["timestamp"] = datetime.utcnow().isoformat()

            if "direction" not in meta:
                meta["direction"] = "inbound"

            # Legacy support for the `data` key instead of `payload`.
            if "payload" not in payload:
                payload["payload"] = payload.get("data", {}) or {}

            return cls.model_validate(payload)

        except Exception as e:
            raise ValueError(f"Parsing error: {e}") from e
