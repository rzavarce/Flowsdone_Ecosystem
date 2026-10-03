"""Messaging window policy: what a business may send to a contact on
each channel, given when that contact last wrote.

Meta's channels (WhatsApp Cloud API, Messenger, Instagram) only accept
free-form messages within 24 hours of the contact's last message. After
that, the official WhatsApp API still allows approved templates, while
Messenger and Instagram allow nothing at all. Channels outside Meta's
rules (Telegram, the console's web chat, WhatsApp through Evolution) have
no such window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Literal, Optional

SendMode = Literal["free_form", "template_required", "not_allowed"]

# What each channel allows once its window has closed (None = it has no window).
WindowRule = Optional[Literal["template_required", "not_allowed"]]

CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)

_RULES: Dict[str, WindowRule] = {
    "whatsapp_360dialog": "template_required",
    "facebook": "not_allowed",
    "instagram": "not_allowed",
    "whatsapp_evolution": None,
    "telegram": None,
    "webchat": None,
}


@dataclass(frozen=True)
class MessagingDecision:
    """What may be sent to a contact right now.

    Attributes:
        mode (SendMode): "free_form" (any message), "template_required"
            (only an approved template) or "not_allowed" (nothing).
        window_closes_at (Optional[datetime]): When the free-form window
            closes; None for channels without a window, or when it is
            already closed / was never opened.
    """

    mode: SendMode
    window_closes_at: Optional[datetime] = None

    @property
    def free_form_allowed(self) -> bool:
        """Whether a free-form message can be sent now.

        Returns:
            bool: True if `mode` is "free_form".
        """
        return self.mode == "free_form"


class MessagingWindowPolicy:
    """Applies each channel's messaging window (see module docstring)."""

    def __init__(self, window: timedelta = CUSTOMER_SERVICE_WINDOW) -> None:
        """Build the policy.

        Args:
            window (timedelta): How long free-form messages are allowed
                after the contact's last message.
        """
        self._window = window

    def decide(self, *, channel_type: str, last_inbound_at: Optional[datetime], now: datetime) -> MessagingDecision:
        """Decide what may be sent to a contact on a channel at `now`.

        Args:
            channel_type (str): The channel the message would go out on.
            last_inbound_at (Optional[datetime]): When the contact last
                wrote on that channel; None if never.
            now (datetime): The current time (timezone-aware).

        Returns:
            MessagingDecision: The allowed mode and, for an open window,
            when it closes. Channels this policy does not know (voice, X,
            TikTok) are "not_allowed": proactive sending is not supported
            there.
        """
        if channel_type not in _RULES:
            return MessagingDecision(mode="not_allowed")

        after_window = _RULES[channel_type]
        if after_window is None:
            return MessagingDecision(mode="free_form")

        if last_inbound_at is not None:
            closes_at = last_inbound_at + self._window
            if now < closes_at:
                return MessagingDecision(mode="free_form", window_closes_at=closes_at)

        return MessagingDecision(mode=after_window)
