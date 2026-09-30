"""Use case for an incoming phone call: which voice channel it belongs to,
and the call session that follows it until it hangs up."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.domain.models.call_session import CallSession
from app.domain.ports.outbound import CallSessionRepositoryPort, ChannelConnectionRepositoryPort

VOICE_CHANNEL = "voice"


class AcceptIncomingCallUseCase:
    """Routes an incoming call to its voice channel and opens its session."""

    def __init__(
        self,
        *,
        channel_connections: ChannelConnectionRepositoryPort,
        call_sessions: CallSessionRepositoryPort,
        session_ttl_seconds: int,
        provider: str,
    ) -> None:
        """Build the use case.

        Args:
            channel_connections (ChannelConnectionRepositoryPort): To find
                the voice channel of the called number.
            call_sessions (CallSessionRepositoryPort): Where the call's
                session lives while it lasts.
            session_ttl_seconds (int): Lifetime of a call session.
            provider (str): Telephony provider name stored on the session.
        """
        self._connections = channel_connections
        self._sessions = call_sessions
        self._ttl = session_ttl_seconds
        self._provider = provider

    async def execute(
        self, *, to_number: str, from_number: str, call_sid: str, now: datetime
    ) -> Optional[CallSession]:
        """Accept a call to `to_number` if a voice channel answers that number.

        Args:
            to_number (str): The number that was called.
            from_number (str): Who calls (a number, or "client:<id>" from a
                browser).
            call_sid (str): The provider's id of the call.
            now (datetime): When it arrived.

        Returns:
            Optional[CallSession]: The saved session (its `config` has the
            channel's voice settings), or None if no active voice channel
            has that number.
        """
        resolution = await self._connections.get_by_channel_and_external_id(VOICE_CHANNEL, to_number)
        if resolution is None:
            return None
        session = CallSession(
            call_sid=call_sid,
            channel_connection_id=resolution.channel_connection_id,
            project_id=resolution.project_id,
            agent_id=resolution.agent_id,
            langflow_flow_id=resolution.langflow_flow_id,
            from_number=from_number,
            to_number=to_number,
            provider=self._provider,
            status="ringing",
            started_at=now,
            config=resolution.config or {},
        )
        await self._sessions.save(session, ttl_seconds=self._ttl)
        return session
