"""Tests for the stub senders (X/Twitter, TikTok): neither platform has
a usable send API for us today, so these must never raise and never
pretend to have delivered anything.
"""

from __future__ import annotations

import logging

import pytest

from api_gateway.app.adapters.outbound.channels.tiktok_sender import TikTokSender
from api_gateway.app.adapters.outbound.channels.twitter_sender import TwitterSender

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("sender_cls,channel", [(TwitterSender, "twitter"), (TikTokSender, "tiktok")])
async def test_stub_sender_logs_not_implemented_and_does_not_raise(caplog, sender_cls, channel):
    with caplog.at_level(logging.WARNING):
        await sender_cls().send(
            external_id="ext-1", recipient_id="user-1", text="hola", credentials={}
        )

    assert any(
        record.message == "channel.sender.not_implemented" and record.channel == channel
        for record in caplog.records
    )
