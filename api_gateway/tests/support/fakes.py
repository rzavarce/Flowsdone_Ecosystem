"""Reusable in-memory fakes for the domain ports, shared across
application-layer tests. Each fake implements just enough of its port
to support the use cases under test — no real I/O, no framework.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from api_gateway.app.domain.models.call_session import CallSession
from api_gateway.app.domain.models.channel_app import ChannelApp
from api_gateway.app.domain.models.channel_connection import ChannelConnection
from api_gateway.app.domain.models.channel_resolution import ChannelResolution
from api_gateway.app.domain.models.voice_relay_event import VoiceRelayEvent


def make_channel_connection(**overrides: Any) -> ChannelConnection:
    """Build a ChannelConnection with sane defaults, overridable per test."""
    now = datetime.now(timezone.utc)
    defaults: Dict[str, Any] = dict(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        channel_type="telegram",
        external_id="123:FAKE-TOKEN",
        display_name=None,
        credentials={},
        config={},
        status="active",
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return ChannelConnection(**defaults)


def make_channel_resolution(**overrides: Any) -> ChannelResolution:
    """Build a ChannelResolution with sane defaults, overridable per test."""
    defaults: Dict[str, Any] = dict(
        tenant_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        langflow_flow_id="flow-123",
        channel_connection_id=uuid4(),
        channel_type="telegram",
        credentials={},
        config={},
    )
    defaults.update(overrides)
    return ChannelResolution(**defaults)


class FakeChannelConnectionRepo:
    """In-memory stand-in for ChannelConnectionRepositoryPort.

    Seed `connections` (a ChannelConnection) and/or `resolution` (a
    ChannelResolution, for the webhook-routing lookup) directly on the
    instance before exercising the use case under test.
    """

    def __init__(
        self,
        connection: Optional[ChannelConnection] = None,
        resolution: Optional[ChannelResolution] = None,
    ) -> None:
        self.connection = connection
        self.resolution = resolution
        self.created: List[Dict[str, Any]] = []
        self.updated: List[Dict[str, Any]] = []
        self.deleted: List[UUID] = []

    async def create(self, **fields: Any) -> ChannelConnection:
        self.created.append(fields)
        self.connection = make_channel_connection(**fields)
        return self.connection

    async def get_by_id(self, channel_connection_id: UUID) -> Optional[ChannelConnection]:
        if self.connection and self.connection.id == channel_connection_id:
            return self.connection
        return None

    async def get_by_channel_and_external_id(
        self, channel_type: str, external_id: str
    ) -> Optional[ChannelResolution]:
        if (
            self.resolution
            and self.resolution.channel_type == channel_type
        ):
            return self.resolution
        return None

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[ChannelConnection]:
        return [self.connection] if self.connection else []

    async def update(self, channel_connection_id: UUID, **fields: Any) -> Optional[ChannelConnection]:
        if not self.connection or self.connection.id != channel_connection_id:
            return None
        self.updated.append(fields)
        update_data = {k: v for k, v in fields.items() if v is not None}
        self.connection = self.connection.model_copy(update=update_data)
        return self.connection

    async def delete(self, channel_connection_id: UUID) -> bool:
        if self.connection and self.connection.id == channel_connection_id:
            self.deleted.append(channel_connection_id)
            self.connection = None
            return True
        return False


class FakeSecretGenerator:
    """Deterministic stand-in for SecretGeneratorPort."""

    def __init__(self, value: str = "generated-secret") -> None:
        self.value = value
        self.calls = 0

    def generate(self) -> str:
        self.calls += 1
        return self.value


class FakeWebhookRegistrar:
    """Configurable stand-in for WebhookRegistrarPort.

    Set `fail=True` to make `register`/`deregister` raise, exercising
    the compensating-action paths of the use cases under test.
    """

    def __init__(self, secret_field: Optional[str] = "the_secret", fail: bool = False) -> None:
        self.secret_field = secret_field
        self.fail = fail
        self.register_calls: List[Dict[str, Any]] = []
        self.deregister_calls: List[Dict[str, Any]] = []

    async def register(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        self.register_calls.append({"external_id": external_id, "credentials": dict(credentials)})
        if self.fail:
            raise RuntimeError("registration rejected by platform")

    async def deregister(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        self.deregister_calls.append({"external_id": external_id, "credentials": dict(credentials)})
        if self.fail:
            raise RuntimeError("deregistration rejected by platform")


class FakePublisher:
    """In-memory stand-in for MessagePublisherPort."""

    def __init__(self) -> None:
        self.published: List[Dict[str, Any]] = []

    async def publish(self, message: Dict[str, Any], *, key: Optional[str] = None) -> None:
        self.published.append({"message": message, "key": key})


class FakePublisherFactory:
    """Stand-in for the publisher factory IngestMessageUseCase depends on."""

    def __init__(self, publisher: Optional[FakePublisher] = None) -> None:
        self.publisher = publisher or FakePublisher()
        self.requested_transports: List[str] = []

    def create(self, transport: str) -> FakePublisher:
        self.requested_transports.append(transport)
        return self.publisher


class FakeWSRegistry:
    """In-memory stand-in for WSRegistry, tracking sent messages instead
    of talking to real WebSocket connections.
    """

    def __init__(self, connected_conversations: Optional[List[str]] = None, fail: bool = False) -> None:
        self._connected = set(connected_conversations or [])
        self.sent: List[Dict[str, Any]] = []
        self.fail = fail

    async def send(self, conversation_id: str, message: dict) -> None:
        if self.fail:
            raise RuntimeError("websocket send failed")
        if conversation_id not in self._connected:
            return
        self.sent.append({"conversation_id": conversation_id, "message": message})


class FakeChannelAppRepo:
    """In-memory stand-in for ChannelAppRepositoryPort.

    Covers both what the inbound webhook handlers (facebook/instagram/
    twitter/tiktok) read via `get_by_provider`, and what the admin
    upsert use case needs: `upsert` replaces `credentials`/`config`
    wholesale, matching SqlAlchemyChannelAppRepository's behavior.
    """

    def __init__(self, channel_app: Optional[Any] = None) -> None:
        self.channel_app = channel_app
        self.upsert_calls: List[Dict[str, Any]] = []

    async def get_by_provider(self, provider: str) -> Optional[Any]:
        return self.channel_app

    async def upsert(self, *, provider: str, credentials: dict, config: dict) -> ChannelApp:
        self.upsert_calls.append({"provider": provider, "credentials": dict(credentials), "config": dict(config)})
        now = datetime.now(timezone.utc)
        self.channel_app = ChannelApp(
            id=self.channel_app.id if self.channel_app else uuid4(),
            provider=provider,
            credentials=credentials,
            config=config,
            created_at=self.channel_app.created_at if self.channel_app else now,
            updated_at=now,
        )
        return self.channel_app


class FakeRouteChannelMessageUseCase:
    """Records calls instead of actually resolving/publishing anything.

    Used to test inbound webhook HTTP handlers in isolation from
    RouteChannelMessageUseCase's own behavior (covered separately in
    tests/application/use_cases/test_route_channel_message.py).
    """

    def __init__(self, not_routable: bool = False) -> None:
        self.not_routable = not_routable
        self.calls: List[Dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.not_routable:
            from api_gateway.app.application.use_cases.route_channel_message import (
                ChannelMessageNotRoutable,
            )

            raise ChannelMessageNotRoutable("no channel_connection matches")


def make_call_session(**overrides: Any) -> CallSession:
    """Build a CallSession with sane defaults, overridable per test."""
    defaults: Dict[str, Any] = dict(
        call_sid="CA123",
        channel_connection_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        langflow_flow_id="flow-123",
        from_number="+15550001111",
        to_number="+15559998888",
        provider="twilio",
        status="ringing",
        started_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return CallSession(**defaults)


class FakeVoiceProvider:
    """Configurable stand-in for VoiceProviderPort.

    `verify_webhook_signature` always returns `signature_valid`;
    `parse_relay_frame` only understands "prompt" (with voicePrompt
    text) and passes every other type through as-is - enough to drive
    the voice inbound routers without a real Twilio payload.
    """

    provider_name = "twilio"

    def __init__(self, signature_valid: bool = True) -> None:
        self.signature_valid = signature_valid
        self.built_twiml_for: List[str] = []
        self.built_twiml_calls: List[Dict[str, Any]] = []
        self.built_frames: List[Dict[str, Any]] = []
        self.built_handoff_for: List[str] = []
        self.built_handoff_calls: List[Dict[str, Any]] = []

    def verify_webhook_signature(
        self, *, url: str, form_params: Dict[str, str], signature: str, auth_token: str
    ) -> bool:
        return self.signature_valid

    def build_twiml_connect(
        self,
        *,
        stream_url: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        tts_provider: Optional[str] = None,
        transcription_language: Optional[str] = None,
        transcription_provider: Optional[str] = None,
        speech_model: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> str:
        self.built_twiml_for.append(stream_url)
        self.built_twiml_calls.append(
            {
                "stream_url": stream_url,
                "voice": voice,
                "language": language,
                "tts_provider": tts_provider,
                "transcription_language": transcription_language,
                "transcription_provider": transcription_provider,
                "speech_model": speech_model,
                "action_url": action_url,
            }
        )
        return f'<Response><Connect><ConversationRelay url="{stream_url}"/></Connect></Response>'

    def parse_relay_frame(self, raw: Dict[str, Any]) -> VoiceRelayEvent:
        frame_type = raw.get("type")
        call_sid = raw.get("callSid", "")
        if frame_type == "prompt":
            return VoiceRelayEvent(
                type="prompt", call_sid=call_sid, text=raw.get("voicePrompt"), raw=raw
            )
        return VoiceRelayEvent(type=frame_type, call_sid=call_sid, raw=raw)

    def build_relay_text_frame(self, *, text: str, last: bool = True) -> Dict[str, Any]:
        frame = {"type": "text", "token": text, "last": last}
        self.built_frames.append(frame)
        return frame

    def build_relay_end_frame(self, *, handoff_data: Dict[str, Any]) -> Dict[str, Any]:
        frame = {"type": "end", "handoffData": json.dumps(handoff_data)}
        self.built_frames.append(frame)
        return frame

    def build_handoff_twiml(self, *, phone_number: str, caller_id: Optional[str] = None) -> str:
        self.built_handoff_for.append(phone_number)
        self.built_handoff_calls.append({"phone_number": phone_number, "caller_id": caller_id})
        return f"<Response><Dial>{phone_number}</Dial></Response>"


class FakeCallSessionRepo:
    """In-memory stand-in for CallSessionRepositoryPort."""

    def __init__(self, session: Optional[CallSession] = None) -> None:
        self.sessions: Dict[str, CallSession] = {}
        if session:
            self.sessions[session.call_sid] = session
        self.saved: List[CallSession] = []
        self.deleted: List[str] = []

    async def save(self, session: CallSession, *, ttl_seconds: int) -> None:
        self.sessions[session.call_sid] = session
        self.saved.append(session)

    async def get(self, call_sid: str) -> Optional[CallSession]:
        return self.sessions.get(call_sid)

    async def delete(self, call_sid: str) -> None:
        self.sessions.pop(call_sid, None)
        self.deleted.append(call_sid)


class FakeChannelSender:
    """In-memory stand-in for ChannelSenderPort."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: List[Dict[str, Any]] = []

    async def send(
        self, *, external_id: str, recipient_id: str, text: str, credentials: Dict[str, Any]
    ) -> None:
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append(
            {
                "external_id": external_id,
                "recipient_id": recipient_id,
                "text": text,
                "credentials": credentials,
            }
        )
