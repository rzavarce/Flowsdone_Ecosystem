"""Tests for the create_user command-line helper (argument and password handling)."""

from __future__ import annotations

import io

import pytest

from app.cli.create_user import parse_args, read_password


def test_parse_args_collects_repeatable_tenants():
    args = parse_args(
        ["--email", "a@x.com", "--name", "A", "--role", "client", "--tenant", "one", "--tenant", "two"]
    )
    assert args.tenant == ["one", "two"] and args.role == "client" and args.password_stdin is False


def test_parse_args_rejects_an_unknown_role():
    with pytest.raises(SystemExit):
        parse_args(["--email", "a@x.com", "--name", "A", "--role", "root"])


def test_there_is_no_password_flag():
    # La contraseña por flag quedaría en el historial del shell y en `ps`.
    with pytest.raises(SystemExit):
        parse_args(["--email", "a@x.com", "--name", "A", "--role", "admin", "--password", "hunter2"])


def test_read_password_from_stdin_strips_the_newline(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("s3cret-passphrase\n"))
    assert read_password(from_stdin=True) == "s3cret-passphrase"


def test_interactive_password_must_match_its_confirmation(monkeypatch):
    answers = iter(["one-passphrase", "another-passphrase"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    with pytest.raises(SystemExit, match="do not match"):
        read_password(from_stdin=False)


def test_interactive_password_returns_when_both_entries_match(monkeypatch):
    answers = iter(["same-passphrase", "same-passphrase"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    assert read_password(from_stdin=False) == "same-passphrase"
