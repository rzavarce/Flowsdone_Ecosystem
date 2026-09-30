"""Tests for the production startup checks (hidden API docs, strong secrets)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.security_checks import (
    InsecureConfigurationError,
    api_docs_urls,
    check_production_settings,
    insecure_secrets,
    is_production,
)

STRONG = "k" * 32


def settings(env="production", admin=STRONG, callback=STRONG + "x"):
    return SimpleNamespace(ENV=env, ADMIN_API_KEY=admin, CALLBACK_HMAC_SECRET=callback)


def test_only_production_is_production():
    assert is_production(settings(env="production")) and is_production(settings(env=" Production "))
    assert not is_production(settings(env="local")) and not is_production(SimpleNamespace())


def test_api_docs_are_hidden_in_production_only():
    assert api_docs_urls(settings()) == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert api_docs_urls(settings(env="local"))["openapi_url"] == "/openapi.json"


@pytest.mark.parametrize(
    "admin, callback, expected",
    [
        ("dev-admin-key-change-me", STRONG, ["ADMIN_API_KEY"]),
        ("ChangeMeAdminApiKey123!", STRONG, ["ADMIN_API_KEY"]),
        (STRONG, "dev-secret-change-me", ["CALLBACK_HMAC_SECRET"]),
        (STRONG, "ChangeMeCallbackHmacSecret123", ["CALLBACK_HMAC_SECRET"]),
        ("", "short", ["ADMIN_API_KEY", "CALLBACK_HMAC_SECRET"]),
        (STRONG, STRONG, []),
    ],
)
def test_weak_secrets_are_detected_by_name(admin, callback, expected):
    assert insecure_secrets(settings(admin=admin, callback=callback)) == expected


def test_production_refuses_to_start_with_a_weak_secret_without_revealing_it():
    with pytest.raises(InsecureConfigurationError) as error:
        check_production_settings(settings(admin="ChangeMeAdminApiKey123!"))

    assert "ADMIN_API_KEY" in str(error.value)
    assert "ChangeMe" not in str(error.value)


def test_outside_production_weak_secrets_are_allowed():
    check_production_settings(settings(env="local", admin="dev-admin-key-change-me"))
    check_production_settings(settings())
