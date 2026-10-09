"""Tests for MessagingWindowPolicy (the 24h customer service window)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.models.messaging_window import MessagingWindowPolicy

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
policy = MessagingWindowPolicy()


@pytest.mark.parametrize("channel", ["whatsapp_360dialog", "facebook", "instagram"])
def test_inside_the_window_free_form_is_allowed_and_the_closing_time_is_known(channel):
    decision = policy.decide(channel_type=channel, last_inbound_at=NOW - timedelta(hours=23), now=NOW)

    assert decision.free_form_allowed
    assert decision.window_closes_at == NOW + timedelta(hours=1)


@pytest.mark.parametrize(
    "channel, after_window",
    [("whatsapp_360dialog", "template_required"), ("facebook", "not_allowed"), ("instagram", "not_allowed")],
)
def test_once_the_window_closes_only_what_the_channel_allows_remains(channel, after_window):
    exactly_24h = policy.decide(channel_type=channel, last_inbound_at=NOW - timedelta(hours=24), now=NOW)
    never_wrote = policy.decide(channel_type=channel, last_inbound_at=None, now=NOW)

    assert exactly_24h.mode == after_window and exactly_24h.window_closes_at is None
    assert never_wrote.mode == after_window


@pytest.mark.parametrize("channel", ["whatsapp_evolution", "telegram", "webchat"])
def test_channels_without_a_window_always_allow_free_form(channel):
    decision = policy.decide(channel_type=channel, last_inbound_at=None, now=NOW)

    assert decision.free_form_allowed and decision.window_closes_at is None


@pytest.mark.parametrize("channel", ["voice", "twitter", "tiktok", "unknown"])
def test_channels_without_proactive_sending_are_not_allowed(channel):
    assert policy.decide(channel_type=channel, last_inbound_at=NOW, now=NOW).mode == "not_allowed"


def test_the_window_length_is_configurable():
    short = MessagingWindowPolicy(window=timedelta(hours=1))

    assert short.decide(channel_type="facebook", last_inbound_at=NOW - timedelta(hours=2), now=NOW).mode == "not_allowed"


def test_chatwoot_follows_metas_rules_for_facebook_and_instagram():
    inside = policy.decide(channel_type="chatwoot", last_inbound_at=NOW - timedelta(hours=1), now=NOW)
    outside = policy.decide(channel_type="chatwoot", last_inbound_at=NOW - timedelta(days=2), now=NOW)

    assert inside.free_form_allowed and outside.mode == "not_allowed"
