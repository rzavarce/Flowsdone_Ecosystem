"""Voice call session domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

CallStatus = Literal["ringing", "in_progress", "completed", "failed"]


class CallSession(BaseModel):
    """Ephemeral state of a single voice call, keyed by call_sid.

    Created when the voice provider's TwiML-equivalent webhook is
    received (before the streaming WebSocket connects), and looked up
    again when that WebSocket opens moments later - the two requests
    do not share process memory, so this is persisted in Redis rather
    than held in-process (see CallSessionRepositoryPort).

    Attributes:
        call_sid (str): Provider-assigned unique id for the call.
        channel_connection_id (UUID): Id of the matched channel
            connection (the specific phone number).
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent that should answer.
        langflow_flow_id (str): Id of the Langflow flow the agent runs.
        from_number (str): Caller's phone number.
        to_number (str): Called phone number (the connection's
            external_id).
        provider (str): Voice provider that owns this call (e.g.
            "twilio"), used to pick the matching VoiceProviderPort
            implementation.
        status (CallStatus): Current lifecycle state of the call.
        started_at (datetime): When the call was first received.
        config (Dict[str, Any]): Snapshot of the channel connection's
            config at call-accept time (voice/language/tts_provider,
            human_transfer_number/human_transfer_phrases) - carried
            here so the streaming WebSocket handler does not need a
            second DB round-trip mid-call.
    """

    call_sid: str
    channel_connection_id: UUID
    project_id: UUID
    agent_id: UUID
    langflow_flow_id: str
    from_number: str
    to_number: str
    provider: str
    status: CallStatus = "ringing"
    started_at: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)
