"""Tests for RandomHexSecretGenerator."""

from __future__ import annotations

from app.adapters.outbound.security.secret_generator import RandomHexSecretGenerator


def test_generates_hex_string_of_expected_length():
    generator = RandomHexSecretGenerator(n_bytes=16)

    secret = generator.generate()

    assert len(secret) == 32  # 2 hex chars per byte
    int(secret, 16)  # raises ValueError if not valid hex


def test_default_length_matches_openssl_rand_hex_32():
    generator = RandomHexSecretGenerator()

    assert len(generator.generate()) == 64  # openssl rand -hex 32 -> 64 hex chars


def test_successive_calls_are_not_repeated():
    generator = RandomHexSecretGenerator()

    secrets_generated = {generator.generate() for _ in range(50)}

    assert len(secrets_generated) == 50
