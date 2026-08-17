"""Switchboard: the platform's single entry point for every inbound
channel turn (text or voice) - resolves or creates the conversation's
Session, dispatches to whichever AppConnectorPort is currently
handling it, and can switch that assignment mid-conversation.

Replaces the old RouteChannelMessageUseCase: same channel-resolution
and conversation_id logic, now backed by an explicit, persisted
Session instead of being recomputed statelessly on every turn.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from app.domain.models.message_envelope import MessageEnvelope, MessageMeta
from app.domain.models.session import Session
from app.domain.ports.outbound import (
    AppConnectorPort,
    ChannelConnectionRepositoryPort,
    SessionHistoryRepositoryPort,
    SessionRepositoryPort,
)
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase

logger = logging.getLogger("switchboard")

DEFAULT_APP = "langflow"


class ChannelMessageNotRoutable(Exception):
    """Raised when no active channel_connection matches (channel_type,
    external_id), or a session references an app no longer registered.
    """


def build_conversation_id(project_id: UUID, channel_type: str, external_conversation_key: str) -> str:
    """Build a deterministic conversation/session id for a channel message.

    Kept byte-for-byte identical to the format every channel has always
    used, so Langflow's own session memory (keyed by this same string)
    is never fragmented by introducing Session.

    Args:
        project_id (UUID): Id of the project the channel connection
            belongs to.
        channel_type (str): Channel type (e.g. "whatsapp_evolution",
            "telegram", "voice").
        external_conversation_key (str): Id of the sender on the
            external platform (remoteJid, psid, chat_id, call_sid, ...).

    Returns:
        str: A conversation id of the form
        "{project_id}:{channel_type}:{external_conversation_key}".
    """
    return f"{project_id}:{channel_type}:{external_conversation_key}"


class Switchboard:
    """Central switching point between inbound channels and destination
    apps (Strategy via AppConnectorPort). See module docstring.
    """

    def __init__(
        self,
        *,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        session_repo: SessionRepositoryPort,
        session_history_repo: SessionHistoryRepositoryPort,
        app_connectors: Dict[str, AppConnectorPort],
        outbound_handler: HandleOutboundResponseUseCase,
        session_ttl_seconds: int,
        default_app: str = DEFAULT_APP,
    ) -> None:
        """Build the switchboard.

        Args:
            channel_connection_repo (ChannelConnectionRepositoryPort):
                Repository used to resolve inbound channel messages.
            session_repo (SessionRepositoryPort): Fast (Redis) live
                session state.
            session_history_repo (SessionHistoryRepositoryPort): Durable
                (Postgres) append-only transcript/event log.
            app_connectors (Dict[str, AppConnectorPort]): Registered
                destination apps, keyed by app_name.
            outbound_handler (HandleOutboundResponseUseCase): Reused to
                deliver a connector's synchronous response, so delivery
                logic (WS/ChannelSenderPort resolution) is never
                duplicated here.
            session_ttl_seconds (int): TTL applied every time a session
                is saved to Redis.
            default_app (str): Which app a brand-new session starts on.
        """
        self.channel_connection_repo = channel_connection_repo
        self.session_repo = session_repo
        self.session_history_repo = session_history_repo
        self.app_connectors = app_connectors
        self.outbound_handler = outbound_handler
        self.session_ttl_seconds = session_ttl_seconds
        self.default_app = default_app

    async def handle_inbound_turn(
        self,
        *,
        channel_type: str,
        external_id: str,
        external_conversation_key: str,
        sender_id: Optional[str],
        message_text: str,
        raw_payload: Dict[str, Any],
    ) -> None:
        """Resolve/create the session for one inbound turn and dispatch
        it to the app currently assigned to that conversation.

        Args:
            channel_type (str): Channel type of the incoming message.
            external_id (str): External id carried by the webhook
                (instance name, page id, bot token, phone number, ...).
            external_conversation_key (str): Id of the sender on the
                external platform (remoteJid, psid, chat_id, call_sid, ...).
            sender_id (Optional[str]): Id of the sender, if different
                from external_conversation_key.
            message_text (str): The caller's message for this turn.
            raw_payload (Dict[str, Any]): The raw, channel-specific
                payload, forwarded to the connector for debugging.

        Raises:
            ChannelMessageNotRoutable: If no active channel_connection
                matches (channel_type, external_id), or the session's
                current app is no longer registered.
        """
        resolution = await self.channel_connection_repo.get_by_channel_and_external_id(
            channel_type, external_id
        )

        if resolution is None:
            logger.warning(
                "switchboard.not_routable",
                extra={"channel_type": channel_type, "external_id": external_id},
            )
            raise ChannelMessageNotRoutable(f"no channel_connection for {channel_type}:{external_id}")

        session_id = build_conversation_id(resolution.project_id, channel_type, external_conversation_key)
        session = await self.session_repo.get(session_id)
        now = datetime.now(timezone.utc)

        if session is None:
            session = Session(
                id=session_id,
                tenant_id=resolution.tenant_id,
                project_id=resolution.project_id,
                channel_type=channel_type,
                channel_connection_id=resolution.channel_connection_id,
                agent_id=resolution.agent_id,
                external_conversation_key=external_conversation_key,
                user_identifier=sender_id or external_conversation_key,
                current_app=self.default_app,
                # Snapshotted once, at creation - stays fixed for the
                # life of the conversation even if the agent's
                # langflow_flow_id changes later (see README).
                variables={"langflow_flow_id": resolution.langflow_flow_id},
                started_at=now,
                last_activity_at=now,
            )
            await self.session_history_repo.append_event(
                session_id=session_id,
                project_id=resolution.project_id,
                event_type="started",
                to_app=session.current_app,
            )
            logger.info(
                "switchboard.session.started",
                extra={"session_id": session_id, "app": session.current_app},
            )

        connector = self.app_connectors.get(session.current_app)
        if connector is None:
            logger.error(
                "switchboard.app_not_registered",
                extra={"session_id": session_id, "app": session.current_app},
            )
            raise ChannelMessageNotRoutable(f"app {session.current_app!r} is not registered")

        await self.session_history_repo.append_message(
            session_id=session_id,
            project_id=resolution.project_id,
            direction="inbound",
            text=message_text,
            app=session.current_app,
        )
        session.record_message(
            direction="inbound", text=message_text, app=session.current_app, timestamp=now
        )

        logger.info(
            "switchboard.turn.dispatched",
            extra={"session_id": session_id, "app": session.current_app},
        )

        result = await connector.handle_turn(
            session=session, message_text=message_text, raw_payload=raw_payload
        )

        await self.session_repo.save(session, ttl_seconds=self.session_ttl_seconds)

        if result is not None:
            await self._deliver_immediately(session, result.text)

    async def switch_app(self, *, session_id: str, to_app: str, reason: Optional[str] = None) -> Session:
        """Switch an in-progress conversation to a different app.

        Infrastructure for future use (no HTTP endpoint wired to this
        yet - there is nothing to switch *to* besides Langflow in this
        feature). No automatic trigger engine calls this either; it is
        meant to be invoked programmatically once real connectors and
        their own switching logic exist.

        Args:
            session_id (str): Conversation id.
            to_app (str): app_name of the destination connector; must
                already be registered.
            reason (Optional[str]): Free-form reason, recorded in the
                history event for audit.

        Returns:
            Session: The updated session.

        Raises:
            ValueError: If `to_app` is not a registered connector.
            ChannelMessageNotRoutable: If no session exists for
                `session_id`.
        """
        if to_app not in self.app_connectors:
            raise ValueError(f"unknown app: {to_app!r}")

        session = await self.session_repo.get(session_id)
        if session is None:
            raise ChannelMessageNotRoutable(f"no session for {session_id!r}")

        from_app = session.current_app
        session.current_app = to_app
        await self.session_repo.save(session, ttl_seconds=self.session_ttl_seconds)
        await self.session_history_repo.append_event(
            session_id=session_id,
            project_id=session.project_id,
            event_type="app_switched",
            from_app=from_app,
            to_app=to_app,
            reason=reason,
        )

        logger.info(
            "switchboard.app_switched",
            extra={"session_id": session_id, "from_app": from_app, "to_app": to_app},
        )

        return session

    async def _deliver_immediately(self, session: Session, text: str) -> None:
        """Deliver a connector's synchronous result right away, reusing
        the existing outbound delivery path (WS/ChannelSenderPort)
        instead of duplicating it.

        Args:
            session (Session): The conversation's current state.
            text (str): Text to deliver back to the caller.
        """
        envelope = MessageEnvelope(
            meta=MessageMeta(
                message_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                direction="outbound",
                conversation_id=session.id,
                channel_connection_id=str(session.channel_connection_id),
                external_conversation_key=session.external_conversation_key,
            ),
            channel=session.channel_type,
            payload={"message": text},
        )
        await self.outbound_handler.deliver(envelope)
