"""Tests for the Fernet encryption of channel credentials at rest."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.adapters.outbound.db import crypto


@pytest.fixture
def key(monkeypatch):
    value = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto.settings, "CHANNEL_CREDENTIALS_ENCRYPTION_KEY", value)
    return value


def test_credentials_round_trip_and_are_not_stored_in_clear(key):
    stored = crypto.encrypt_credentials({"page_access_token": "EAAB-secret", "n": 1})

    assert set(stored) == {"ciphertext"}
    assert "EAAB-secret" not in stored["ciphertext"]
    assert crypto.decrypt_credentials(stored) == {"page_access_token": "EAAB-secret", "n": 1}


def test_nothing_stored_decrypts_to_empty(key):
    assert crypto.decrypt_credentials({}) == {}
    assert crypto.decrypt_credentials({"ciphertext": ""}) == {}


def test_a_different_key_cannot_read_them(key, monkeypatch):
    stored = crypto.encrypt_credentials({"token": "x"})
    monkeypatch.setattr(crypto.settings, "CHANNEL_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())

    with pytest.raises(InvalidToken):
        crypto.decrypt_credentials(stored)


def test_without_a_key_it_refuses_to_work(monkeypatch):
    monkeypatch.setattr(crypto.settings, "CHANNEL_CREDENTIALS_ENCRYPTION_KEY", None)

    with pytest.raises(RuntimeError, match="CHANNEL_CREDENTIALS_ENCRYPTION_KEY"):
        crypto.encrypt_credentials({"token": "x"})
