"""Real-time voice streaming WebSocket.

The provider opens this connection right after the incoming-call
webhook returns its call-control markup, and keeps it open for the
whole call, exchanging one frame per conversational turn (and a few
control frames) instead of one request per turn.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .....application.services.switchboard import ChannelMessageNotRoutable
from .....domain.models.call_session import CallSession
from .webhook import CHANNEL_TYPE

logger = logging.getLogger("channels.voice.stream")

router = APIRouter()


def _matches_human_transfer_phrase(text: str, phrases: List[str]) -> bool:
    """Check a transcribed utterance against a deterministic trigger list.

    Deliberately not left to the LLM: this exists to satisfy a legal
    requirement to always offer a human option, so the trigger must be
    reliable/auditable rather than dependent on the agent's judgment.
    Plain case-insensitive substring matching - no fuzzy matching or
    accent normalization yet, see README section 18.

    Args:
        text (str): The caller's transcribed utterance.
        phrases (List[str]): Trigger phrases configured on the
            channel_connection (human_transfer_phrases).

    Returns:
        bool: True if any configured phrase appears in `text`.
    """
    normalized = text.strip().lower()
    return any(phrase.strip().lower() in normalized for phrase in phrases if phrase.strip())


@router.websocket("/voice/stream/{call_sid}")
async def stream_endpoint(ws: WebSocket, call_sid: str) -> None:
    """Handle one call's real-time streaming session end to end.

    Looks up the CallSession created by the incoming-call webhook,
    registers the live connection in call_session_registry (so
    TwilioVoiceSender can push the agent's responses back onto it),
    and routes each transcribed user turn through the same
    channel-agnostic pipeline every other channel uses.

    Args:
        ws (WebSocket): The FastAPI WebSocket connection.
        call_sid (str): Provider-assigned unique id for the call, from
            the path this application itself generated in webhook.py.
    """
    await ws.accept()

    call_session_repo = ws.app.state.call_session_repo
    call_session_registry = ws.app.state.call_session_registry
    voice_provider = ws.app.state.voice_provider
    switchboard = ws.app.state.switchboard

    session = await call_session_repo.get(call_sid)
    if session is None:
        logger.warning("channels.voice.stream.unknown_call", extra={"call_sid": call_sid})
        await ws.close(code=1008)
        return

    call_session_registry.add(call_sid, ws)
    logger.info("channels.voice.stream.connected", extra={"call_sid": call_sid})

    try:
        while True:
            raw_frame = await ws.receive_json()

            try:
                event = voice_provider.parse_relay_frame(raw_frame)
            except ValueError:
                logger.warning(
                    "channels.voice.stream.unparseable_frame", extra={"call_sid": call_sid}
                )
                continue

            if event.type == "prompt" and event.text:
                transfer_number = session.config.get("human_transfer_number")
                phrases = session.config.get("human_transfer_phrases") or []

                if transfer_number and _matches_human_transfer_phrase(event.text, phrases):
                    logger.info(
                        "channels.voice.stream.human_transfer_triggered",
                        extra={"call_sid": call_sid},
                    )
                    end_frame = voice_provider.build_relay_end_frame(
                        handoff_data={
                            "reason": "human_transfer",
                            "transfer_number": transfer_number,
                            "caller_id": session.to_number,
                        }
                    )
                    await ws.send_json(end_frame)
                    break

                await _route_turn(switchboard, session, event.text, raw_frame)
            elif event.type == "end":
                break

    except WebSocketDisconnect:
        logger.info("channels.voice.stream.disconnected", extra={"call_sid": call_sid})
    finally:
        call_session_registry.remove(call_sid)
        await call_session_repo.delete(call_sid)


async def _route_turn(
    switchboard: Any,
    session: CallSession,
    text: str,
    raw_frame: Dict[str, Any],
) -> None:
    """Route a single transcribed caller utterance to its currently
    assigned app.

    No `transport` to pick here: Switchboard's LangflowAppConnector
    infers "kafka_voice" on its own from channel_type="voice" - voice
    and every other channel go through the exact same call.

    Args:
        switchboard (Any): The Switchboard instance.
        session (CallSession): The call's session context.
        text (str): Transcribed caller speech.
        raw_frame (Dict[str, Any]): The raw provider frame, kept in the
            payload for debugging.
    """
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=session.to_number,
            external_conversation_key=session.call_sid,
            sender_id=session.from_number,
            message_text=text,
            raw_payload=raw_frame,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.voice.not_routable",
            extra={"call_sid": session.call_sid, "to": session.to_number},
        )
    except Exception:
        logger.exception("channels.voice.routing_failed")
