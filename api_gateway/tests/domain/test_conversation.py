"""Tests for ConversationLifecyclePolicy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.models.conversation import ConversationLifecyclePolicy
from api_gateway.tests.support.fakes import make_conversation

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
POLICY = ConversationLifecyclePolicy(inactivity=timedelta(hours=24), max_duration=timedelta(days=7))


def test_expires_by_inactivity_24h_after_the_last_inbound_message():
    conversation = make_conversation(started_at=T0, last_inbound_at=T0 + timedelta(hours=5))

    expiry = POLICY.expiry(conversation)

    assert expiry.reason == "inactivity"
    assert expiry.at == T0 + timedelta(hours=29)


def test_expires_by_max_duration_when_the_contact_keeps_writing():
    conversation = make_conversation(started_at=T0, last_inbound_at=T0 + timedelta(days=6, hours=23))

    expiry = POLICY.expiry(conversation)

    assert expiry.reason == "max_duration"
    assert expiry.at == T0 + timedelta(days=7)


def test_max_duration_wins_a_tie():
    conversation = make_conversation(started_at=T0, last_inbound_at=T0 + timedelta(days=6))

    assert POLICY.expiry(conversation).reason == "max_duration"


def test_is_expired_only_from_the_expiry_moment_on():
    conversation = make_conversation(started_at=T0, last_inbound_at=T0)

    assert not POLICY.is_expired(conversation, T0 + timedelta(hours=23, minutes=59))
    assert POLICY.is_expired(conversation, T0 + timedelta(hours=24))


def test_a_closed_conversation_is_always_expired():
    conversation = make_conversation(started_at=T0, last_inbound_at=T0, status="closed")

    assert POLICY.is_expired(conversation, T0)
