"""Reusable in-memory fakes for the domain ports, shared across
application-layer tests. Each fake implements just enough of its port
to support the use cases under test — no real I/O, no framework.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.models.call_session import CallSession
from app.domain.models.channel_app import ChannelApp
from app.domain.models.channel_connection import ChannelConnection
from app.domain.models.tenant_billing_profile import TenantBillingProfile
from app.domain.models.channel_resolution import ChannelResolution
from app.domain.models.session import Session
from app.domain.models.tenant import Tenant
from app.domain.models.user import User, UserCredentials
from app.domain.ports.outbound import AlreadyExistsError, UserAlreadyExistsError
from app.domain.models.voice_relay_event import VoiceRelayEvent


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
        tts_language: Optional[str] = None,
        transcription_language: Optional[str] = None,
        transcription_provider: Optional[str] = None,
        speech_model: Optional[str] = None,
        action_url: Optional[str] = None,
        welcome_greeting: Optional[str] = None,
    ) -> str:
        self.built_twiml_for.append(stream_url)
        self.built_twiml_calls.append(
            {
                "stream_url": stream_url,
                "voice": voice,
                "language": language,
                "tts_provider": tts_provider,
                "tts_language": tts_language,
                "transcription_language": transcription_language,
                "transcription_provider": transcription_provider,
                "speech_model": speech_model,
                "action_url": action_url,
                "welcome_greeting": welcome_greeting,
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

    def build_relay_text_frame(
        self, *, text: str, last: bool = True, lang: Optional[str] = None
    ) -> Dict[str, Any]:
        frame: Dict[str, Any] = {"type": "text", "token": text, "last": last}
        if lang:
            frame["lang"] = lang
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


class FakeRedisClient:
    """Minimal in-memory stand-in for redis.asyncio.Redis, only the
    get/set/delete/expire/incr/sets subset the Redis-backed repositories use.
    """

    def __init__(self) -> None:
        self.store: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}
        self.sets: Dict[str, set] = {}

    async def set(self, key: str, value: str, *, ex: Optional[int] = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def getdel(self, key: str) -> Optional[str]:
        self.ttls.pop(key, None)
        return self.store.pop(key, None)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        self.sets.pop(key, None)

    async def expire(self, key: str, seconds: int) -> None:
        if key in self.store or key in self.sets:
            self.ttls[key] = seconds

    async def incr(self, key: str) -> int:
        value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(value)
        return value

    async def sadd(self, key: str, member: str) -> None:
        self.sets.setdefault(key, set()).add(member)

    async def srem(self, key: str, member: str) -> None:
        self.sets.get(key, set()).discard(member)

    async def smembers(self, key: str) -> set:
        return set(self.sets.get(key, set()))


def make_session(**overrides: Any) -> Session:
    """Build a Session with sane defaults, overridable per test."""
    now = datetime.now(timezone.utc)
    defaults: Dict[str, Any] = dict(
        id=f"{uuid4()}:telegram:chat-1",
        tenant_id=uuid4(),
        project_id=uuid4(),
        channel_type="telegram",
        channel_connection_id=uuid4(),
        agent_id=uuid4(),
        external_conversation_key="chat-1",
        user_identifier="user-1",
        current_app="langflow",
        variables={},
        last_messages=[],
        started_at=now,
        last_activity_at=now,
        status="active",
    )
    defaults.update(overrides)
    return Session(**defaults)


class FakeSessionRepository:
    """In-memory stand-in for SessionRepositoryPort."""

    def __init__(self, session: Optional[Session] = None) -> None:
        self.sessions: Dict[str, Session] = {}
        if session:
            self.sessions[session.id] = session
        self.saved: List[Session] = []
        self.deleted: List[str] = []

    async def get(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    async def save(self, session: Session, *, ttl_seconds: int) -> None:
        self.sessions[session.id] = session
        self.saved.append(session)

    async def delete(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.deleted.append(session_id)


class FakeSessionHistoryRepository:
    """In-memory stand-in for SessionHistoryRepositoryPort."""

    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    async def append_message(
        self, *, session_id: str, project_id: UUID, direction: str, text: str, app: str
    ) -> None:
        self.messages.append(
            {
                "session_id": session_id,
                "project_id": project_id,
                "direction": direction,
                "text": text,
                "app": app,
            }
        )

    async def append_event(
        self,
        *,
        session_id: str,
        project_id: UUID,
        event_type: str,
        from_app: Optional[str] = None,
        to_app: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        self.events.append(
            {
                "session_id": session_id,
                "project_id": project_id,
                "event_type": event_type,
                "from_app": from_app,
                "to_app": to_app,
                "reason": reason,
            }
        )


class FakeAppConnector:
    """Configurable stand-in for AppConnectorPort."""

    def __init__(self, app_name: str = "langflow", result: Optional[Any] = None) -> None:
        self.app_name = app_name
        self.result = result
        self.calls: List[Dict[str, Any]] = []

    async def handle_turn(
        self, *, session: Session, message_text: str, raw_payload: Dict[str, Any]
    ) -> Optional[Any]:
        self.calls.append(
            {"session": session, "message_text": message_text, "raw_payload": raw_payload}
        )
        return self.result


class FakeSwitchboard:
    """Records calls instead of actually resolving/dispatching anything.

    Used to test inbound webhook HTTP handlers in isolation from
    Switchboard's own behavior (covered separately in
    tests/application/services/test_switchboard.py).
    """

    def __init__(self, not_routable: bool = False) -> None:
        self.not_routable = not_routable
        self.calls: List[Dict[str, Any]] = []

    async def handle_inbound_turn(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.not_routable:
            from app.application.services.switchboard import (
                ChannelMessageNotRoutable,
            )

            raise ChannelMessageNotRoutable("no channel_connection matches")


class FakeOutboundHandler:
    """Records delivered envelopes instead of actually delivering them.

    Stands in for HandleOutboundResponseUseCase where only
    Switchboard._deliver_immediately()'s call to deliver() matters.
    """

    def __init__(self) -> None:
        self.delivered: List[Any] = []

    async def deliver(self, envelope: Any) -> None:
        self.delivered.append(envelope)


# --------------------------------------------------------------------------
# Console authentication
# --------------------------------------------------------------------------


def make_tenant(**overrides: Any) -> Tenant:
    """Build a Tenant with sane defaults, overridable per test."""
    now = datetime.now(timezone.utc)
    defaults: Dict[str, Any] = dict(
        id=uuid4(), name="Clínica Vital", slug="clinica-vital", created_at=now, updated_at=now
    )
    defaults.update(overrides)
    return Tenant(**defaults)


def make_user(**overrides: Any) -> User:
    """Build a User (role `client`, active, no tenants) with sane defaults."""
    now = datetime.now(timezone.utc)
    defaults: Dict[str, Any] = dict(
        id=uuid4(),
        email="carla@cliente.com",
        name="Carla Cliente",
        role="client",
        status="active",
        tenant_ids=[],
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return User(**defaults)


class FakeTenantRepo:
    """In-memory TenantRepositoryPort: create/list/list_by_ids/get_by_id."""

    def __init__(self, tenants: Optional[List[Tenant]] = None) -> None:
        self.tenants = list(tenants or [])

    async def create(self, *, name: str, slug: str) -> Tenant:
        if any(t.slug == slug for t in self.tenants):
            raise AlreadyExistsError(slug)
        tenant = make_tenant(name=name, slug=slug)
        self.tenants.append(tenant)
        return tenant

    async def list(self) -> List[Tenant]:
        return list(self.tenants)

    async def list_by_ids(self, tenant_ids: List[UUID]) -> List[Tenant]:
        return [t for t in self.tenants if t.id in tenant_ids]

    async def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        return next((t for t in self.tenants if t.id == tenant_id), None)


class FakePasswordHasher:
    """Instant, reversible stand-in for the real (slow) scrypt hasher."""

    def __init__(self) -> None:
        self.verify_calls: List[str] = []

    def hash(self, password: str) -> str:
        return f"fake${password}"

    def verify(self, password: str, password_hash: str) -> bool:
        self.verify_calls.append(password_hash)
        return password_hash == f"fake${password}"


class FakeUserRepo:
    """In-memory UserRepositoryPort."""

    def __init__(self) -> None:
        self.users: Dict[UUID, User] = {}
        self.hashes: Dict[UUID, str] = {}
        self.logins: List[UUID] = []

    def add(self, user: User, password: str = "correct-horse-battery") -> User:
        """Test helper: register a user with a fake-hashed password."""
        self.users[user.id] = user
        self.hashes[user.id] = f"fake${password}"
        return user

    async def create(self, *, email, name, role, password_hash, tenant_ids, status="active") -> User:
        if any(u.email == email for u in self.users.values()):
            raise UserAlreadyExistsError(email)
        user = make_user(email=email, name=name, role=role, tenant_ids=list(tenant_ids), status=status)
        self.users[user.id] = user
        self.hashes[user.id] = password_hash
        return user

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return self.users.get(user_id)

    async def get_credentials_by_email(self, email: str) -> Optional[UserCredentials]:
        for user in self.users.values():
            if user.email == email.lower():
                return UserCredentials(user=user, password_hash=self.hashes[user.id])
        return None

    async def mark_login(self, user_id: UUID) -> None:
        self.logins.append(user_id)

    async def list(self) -> List[User]:
        return list(self.users.values())

    async def update(self, user_id, *, name=None, role=None, status=None, tenant_ids=None, password_hash=None):
        user = self.users.get(user_id)
        if user is None:
            return None
        changes = {k: v for k, v in dict(name=name, role=role, status=status, tenant_ids=tenant_ids).items() if v is not None}
        self.users[user_id] = user.model_copy(update=changes)
        if password_hash is not None:
            self.hashes[user_id] = password_hash
        return self.users[user_id]

    async def delete(self, user_id: UUID) -> bool:
        self.hashes.pop(user_id, None)
        return self.users.pop(user_id, None) is not None


class FakeAuthSessionRepo:
    """In-memory AuthSessionRepositoryPort."""

    def __init__(self) -> None:
        self.sessions: Dict[str, UUID] = {}
        self.ttls: Dict[str, int] = {}
        self._n = 0

    async def create(self, user_id: UUID, *, ttl_seconds: int) -> str:
        self._n += 1
        token = f"token-{self._n}"
        self.sessions[token] = user_id
        self.ttls[token] = ttl_seconds
        return token

    async def get_user_id(self, token: str, *, ttl_seconds: int) -> Optional[UUID]:
        user_id = self.sessions.get(token)
        if user_id is not None:
            self.ttls[token] = ttl_seconds
        return user_id

    async def delete(self, token: str) -> None:
        self.sessions.pop(token, None)

    async def delete_all_for_user(self, user_id: UUID) -> None:
        for token in [t for t, u in self.sessions.items() if u == user_id]:
            del self.sessions[token]


class FakeLoginThrottle:
    """In-memory LoginThrottlePort (no real expiry: windows are recorded)."""

    def __init__(self) -> None:
        self.counts: Dict[str, int] = {}
        self.windows: Dict[str, int] = {}

    async def failures(self, key: str) -> int:
        return self.counts.get(key, 0)

    async def record_failure(self, key: str, *, window_seconds: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        self.windows[key] = window_seconds
        return self.counts[key]

    async def reset(self, key: str) -> None:
        self.counts.pop(key, None)


class FakeAccountTokenStore:
    """In-memory AccountTokenStorePort (no real expiry: `issue` just stores).

    One instance per "kind" of token in a test, same as the real
    `RedisAccountTokenStore` - a token issued by one instance is unknown to
    another, mirroring the activate/reset key-prefix separation.
    """

    def __init__(self) -> None:
        self.tokens: Dict[str, UUID] = {}

    async def issue(self, user_id: UUID, *, ttl_seconds: int) -> str:
        token = f"token-{uuid4()}"
        self.tokens[token] = user_id
        return token

    async def redeem(self, token: str) -> Optional[UUID]:
        return self.tokens.pop(token, None)


class FakeEmailSender:
    """In-memory EmailSenderPort: records every call instead of sending anything."""

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    async def send_template(self, *, to: str, template: str, context: Dict[str, Any], subject: str) -> None:
        self.sent.append({"to": to, "template": template, "context": context, "subject": subject})


class FakeTenantBillingProfileRepo:
    """In-memory TenantBillingProfileRepositoryPort."""

    def __init__(self) -> None:
        self.profiles: Dict[UUID, TenantBillingProfile] = {}

    async def get_by_tenant_id(self, tenant_id: UUID) -> Optional[TenantBillingProfile]:
        return self.profiles.get(tenant_id)

    async def upsert(self, tenant_id: UUID, **fields: Any) -> TenantBillingProfile:
        now = datetime.now(timezone.utc)
        current = self.profiles.get(tenant_id)
        if current is None:
            profile = TenantBillingProfile(
                id=uuid4(), tenant_id=tenant_id, created_at=now, updated_at=now,
                **{k: v for k, v in fields.items() if v is not None},
            )
        else:
            changes = {k: v for k, v in fields.items() if v is not None}
            profile = current.model_copy(update={**changes, "updated_at": now})
        self.profiles[tenant_id] = profile
        return profile
