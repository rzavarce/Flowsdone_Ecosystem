"""Use case for turning a Langflow result into a delivered response."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from app.domain.models.message_envelope import MessageEnvelope
from app.domain.ports.outbound import (
    ChannelConnectionRepositoryPort,
    ChannelSenderPort,
    SessionHistoryRepositoryPort,
    SessionRepositoryPort,
)
from app.application.services.langflow_result import extract_text_from_langflow_result

logger = logging.getLogger("usecase.handle_outbound_response")


class HandleOutboundResponseUseCase:
    """Processes a workflow result and delivers it to the caller.

    Responsibilities:
        - Extract the response text from a Langflow result.
        - Optionally forward it to a callback URL.
        - Publish an outbound MessageEnvelope to the broker.
        - Deliver the final response to WebSocket and/or the native
          channel sender that corresponds to the conversation.
    """

    def __init__(
        self,
        publisher: Optional[Any] = None,
        ws_registry: Optional[Any] = None,
        channel_connection_repo: Optional[ChannelConnectionRepositoryPort] = None,
        channel_senders: Optional[Dict[str, ChannelSenderPort]] = None,
        session_repo: Optional[SessionRepositoryPort] = None,
        session_history_repo: Optional[SessionHistoryRepositoryPort] = None,
        session_ttl_seconds: int = 86400,
    ):
        """Build the use case.

        Args:
            publisher (Optional[Any]): Broker publisher for the
                outbound envelope.
            ws_registry (Optional[Any]): WebSocket registry used to
                push responses to webchat clients.
            channel_connection_repo (Optional[ChannelConnectionRepositoryPort]):
                Repository used to resolve a channel connection's
                credentials on delivery.
            channel_senders (Optional[Dict[str, ChannelSenderPort]]):
                Map of channel_type to its sender, used to deliver to
                native channels.
            session_repo (Optional[SessionRepositoryPort]): Fast (Redis)
                session state, used to record the delivered turn.
                Optional - webchat delivery has no Session (it never
                goes through Switchboard) and callers/tests that don't
                need history recording can omit it.
            session_history_repo (Optional[SessionHistoryRepositoryPort]):
                Durable (Postgres) transcript, appended to on delivery.
            session_ttl_seconds (int): TTL applied when re-saving the
                session after recording a delivered turn.
        """
        self.publisher = publisher
        self.ws_registry = ws_registry
        self.channel_connection_repo = channel_connection_repo
        self.channel_senders = channel_senders or {}
        self.session_repo = session_repo
        self.session_history_repo = session_history_repo
        self.session_ttl_seconds = session_ttl_seconds

    def _extract_text(self, value: Any) -> Optional[str]:
        """Recursively extract a human-readable response string.

        Thin wrapper around the shared
        `application.services.langflow_result.extract_text_from_langflow_result`,
        kept as a method for backward compatibility with existing
        callers/tests.

        Args:
            value (Any): A Langflow result, or a nested part of one.

        Returns:
            Optional[str]: The extracted text, or None if no text
            could be found.
        """
        return extract_text_from_langflow_result(value)

    async def execute(
        self,
        envelope: MessageEnvelope,
        result: Dict[str, Any],
    ) -> None:
        """Process a Langflow result and publish the outbound response.

        Builds the response payload, optionally posts it to the
        envelope's callback_url, pushes it to WebSocket if the
        conversation has a live connection, and publishes an outbound
        MessageEnvelope to the broker for the outbound worker to pick
        up (which in turn calls deliver()).

        Args:
            envelope (MessageEnvelope): The inbound envelope that was processed.
            result (Dict[str, Any]): The raw result returned by the
                Langflow executor.
        """
        response_message = self._extract_text(result)

        if not response_message:
            logger.error(
                "handle.outbound.invalid_langflow_response",
                extra={
                    "message_id": envelope.meta.message_id,
                    "result_preview": str(result)[:1000],
                },
            )
            response_message = "The workflow did not return a valid response."

        response_payload = {
            "type": "chat.response",
            "response": response_message,
            "message": response_message,
        }

        logger.info(
            "handle.outbound.response.built",
            extra={"message_id": envelope.meta.message_id},
        )

        # Optional HTTP callback.
        callback_url = None

        try:
            callback_url = envelope.payload.get("callback_url")
        except Exception:
            pass

        if callback_url:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        callback_url,
                        json={
                            "conversation_id": envelope.meta.conversation_id,
                            "message": response_message,
                        },
                    )

                logger.info(
                    "handle.outbound.callback.sent",
                    extra={
                        "url": callback_url,
                        "message_id": envelope.meta.message_id,
                    },
                )

            except Exception as e:
                logger.error(
                    "handle.outbound.callback.failed",
                    extra={
                        "url": callback_url,
                        "message_id": envelope.meta.message_id,
                    },
                    exc_info=e,
                )
        else:
            logger.debug(
                "handle.outbound.callback.not_present",
                extra={"message_id": envelope.meta.message_id},
            )

        # Push to WebSocket if the conversation has a live connection.
        if getattr(self, "ws_registry", None) and envelope.meta.conversation_id:
            try:
                await self.ws_registry.send(
                    conversation_id=envelope.meta.conversation_id,
                    message=response_payload,
                )

                logger.info(
                    "handle.outbound.ws.sent",
                    extra={
                        "conversation_id": envelope.meta.conversation_id,
                    },
                )

            except Exception:
                logger.error("handle.outbound.ws.failed", exc_info=True)

        # Build and publish the outbound envelope.
        try:
            response_envelope = MessageEnvelope(
                meta=envelope.meta.model_copy(update={"direction": "outbound"}),
                transport=envelope.transport,
                channel=envelope.channel,
                payload=response_payload,
                response_to=envelope.meta.message_id,
            )
        except Exception:
            logger.error("handle.outbound.envelope.build.failed", exc_info=True)
            return

        if self.publisher:
            try:
                await self.publisher.publish(
                    response_envelope.model_dump(), key=response_envelope.channel
                )

                logger.info(
                    "handle.outbound.message.published",
                    extra={
                        "conversation_id": envelope.meta.conversation_id,
                    },
                )
            except Exception:
                logger.error("handle.outbound.publish.failed", exc_info=True)

    async def deliver(self, envelope: MessageEnvelope) -> None:
        """Deliver an already-processed outbound envelope.

        Called from /internal/outbound when the Kafka or RabbitMQ
        worker forwards a response back to the gateway.

        - If it came from webchat, dispatches it over WebSocket
          (unchanged from the original behavior).
        - If it came from a native channel (channel_connection_id
          present), sends it back to that channel with the
          corresponding sender.

        Args:
            envelope (MessageEnvelope): The outbound envelope to deliver.
        """
        if self.ws_registry and envelope.meta.conversation_id:
            try:
                await self.ws_registry.send(
                    conversation_id=envelope.meta.conversation_id,
                    message={
                        "type": "chat.response",
                        "message": envelope.payload.get("message", ""),
                    },
                )
                logger.info(
                    "handle.outbound.ws.delivered",
                    extra={"conversation_id": envelope.meta.conversation_id},
                )
            except Exception:
                logger.error("handle.outbound.ws.deliver.failed", exc_info=True)

        await self._deliver_to_channel(envelope)

    async def _deliver_to_channel(self, envelope: MessageEnvelope) -> None:
        """Send an outbound envelope to its originating native channel.

        No-ops if the envelope has no channel_connection_id (webchat)
        or no matching sender is configured. Never raises: a delivery
        failure is logged, not propagated, so it cannot break the
        /internal/outbound request.

        Args:
            envelope (MessageEnvelope): The outbound envelope to deliver.
        """
        channel_connection_id = envelope.meta.channel_connection_id
        if not channel_connection_id or not self.channel_connection_repo:
            return

        sender = self.channel_senders.get(envelope.channel or "")
        if not sender:
            return

        try:
            connection = await self.channel_connection_repo.get_by_id(
                UUID(channel_connection_id)
            )
            if not connection:
                logger.warning(
                    "handle.outbound.channel.connection_not_found",
                    extra={"channel_connection_id": channel_connection_id},
                )
                return

            text = envelope.payload.get("message", "")
            await sender.send(
                external_id=connection.external_id,
                recipient_id=envelope.meta.external_conversation_key or "",
                text=text,
                credentials=connection.credentials,
            )

            logger.info(
                "handle.outbound.channel.delivered",
                extra={
                    "channel": envelope.channel,
                    "channel_connection_id": channel_connection_id,
                },
            )

            await self._record_outbound_turn(envelope.meta.conversation_id, text)
        except Exception:
            logger.error("handle.outbound.channel.deliver.failed", exc_info=True)

    async def _record_outbound_turn(self, conversation_id: Optional[str], text: str) -> None:
        """Best-effort: append the delivered turn to the session's
        history and touch its fast-state rolling window, if session
        ports are wired and a session exists for this conversation.

        Never raises - a failure here must not undo an already-delivered
        message. No-ops silently when session_repo/session_history_repo
        were not provided (e.g. webchat delivery, which has no Session)
        or no session is found.

        Args:
            conversation_id (Optional[str]): The session id to record
                against.
            text (str): The text that was just delivered.
        """
        if not self.session_repo or not self.session_history_repo or not conversation_id:
            return

        try:
            session = await self.session_repo.get(conversation_id)
            if session is None:
                return

            await self.session_history_repo.append_message(
                session_id=conversation_id,
                project_id=session.project_id,
                direction="outbound",
                text=text,
                app=session.current_app,
            )
            session.record_message(
                direction="outbound",
                text=text,
                app=session.current_app,
                timestamp=datetime.now(timezone.utc),
            )
            await self.session_repo.save(session, ttl_seconds=self.session_ttl_seconds)
        except Exception:
            logger.error("handle.outbound.session_record.failed", exc_info=True)
