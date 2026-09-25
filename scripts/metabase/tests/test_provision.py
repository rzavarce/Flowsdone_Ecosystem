"""Tests for scripts/metabase/provision.py (Metabase answered by an httpx MockTransport).

Run: pytest scripts/metabase/tests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import provision  # noqa: E402

ENV = {
    "METABASE_ADMIN_EMAIL": "admin@flowsdone.com",
    "METABASE_ADMIN_PASSWORD": "pw",
    "METABASE_READER_PASSWORD": "pg-pw",
    "CLICKHOUSE_METABASE_PASSWORD": "ch-pw",
}


class FakeMetabase:
    """Minimal in-memory Metabase API: setup, session and databases."""

    def __init__(self, *, set_up: bool = False) -> None:
        self.set_up = set_up
        self.databases = [{"id": 1, "name": "Sample Database", "engine": "h2", "is_sample": True}]
        self.calls: list = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else None
        self.calls.append((method, path, body))
        if path == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/session/properties":
            return httpx.Response(200, json={"has-user-setup": self.set_up, "setup-token": "tok"})
        if path == "/api/setup":
            self.set_up = True
            return httpx.Response(200, json={"id": "session"})
        if path == "/api/session":
            ok = body == {"username": ENV["METABASE_ADMIN_EMAIL"], "password": ENV["METABASE_ADMIN_PASSWORD"]}
            return httpx.Response(200 if ok else 401, json={"id": "session"})
        if request.headers.get("x-metabase-session") != "session":
            return httpx.Response(401)
        if path == "/api/database" and method == "GET":
            return httpx.Response(200, json={"data": self.databases})
        if path == "/api/database" and method == "POST":
            db = {"id": len(self.databases) + 10, **body}
            self.databases.append(db)
            return httpx.Response(200, json=db)
        if path.startswith("/api/database/"):
            db_id = int(path.rsplit("/", 1)[1])
            if method == "DELETE":
                self.databases = [d for d in self.databases if d["id"] != db_id]
                return httpx.Response(204)
            if method == "PUT":
                return httpx.Response(200, json={"id": db_id, **body})
        return httpx.Response(404)


def _run(fake: FakeMetabase, env=ENV):
    config = provision.Config.from_env(env)
    client = httpx.Client(base_url=config.url, transport=httpx.MockTransport(fake.handle))
    provision.wait_until_ready(client, attempts=1, delay=0)
    done = provision.ensure_setup(client, config)
    provision.login(client, config)
    removed = provision.remove_sample_database(client)
    return done, removed, provision.ensure_sources(client, config)


def test_first_run_sets_up_removes_the_sample_and_connects_read_only_sources():
    fake = FakeMetabase()

    done, removed, ids = _run(fake)

    assert done is True and removed is True
    setup = next(body for method, path, body in fake.calls if path == "/api/setup")
    assert setup["token"] == "tok" and setup["user"]["email"] == "admin@flowsdone.com"
    assert setup["prefs"]["allow_tracking"] is False
    by_name = {d["name"]: d for d in fake.databases}
    assert set(by_name) == {provision.POSTGRES_SOURCE, provision.CLICKHOUSE_SOURCE}
    pg = by_name[provision.POSTGRES_SOURCE]["details"]
    assert (pg["user"], pg["password"], pg["dbname"]) == ("metabase_reader", "pg-pw", "gatewaydb")
    assert pg["schema-filters-type"] == "inclusion" and pg["schema-filters-patterns"] == "analytics"
    ch = by_name[provision.CLICKHOUSE_SOURCE]["details"]
    assert (ch["user"], ch["password"], ch["dbname"]) == ("metabase_reader", "ch-pw", "flowsdone")
    assert set(ids) == set(by_name)


def test_a_second_run_updates_instead_of_duplicating():
    fake = FakeMetabase()
    _run(fake)
    fake.calls.clear()

    done, removed, _ = _run(fake, {**ENV, "METABASE_READER_PASSWORD": "rotated"})

    assert done is False and removed is False
    assert len(fake.databases) == 2
    puts = [body for method, path, body in fake.calls if method == "PUT"]
    assert len(puts) == 2 and any(b["details"]["password"] == "rotated" for b in puts)


def test_missing_variables_and_wrong_credentials_fail_clearly():
    with pytest.raises(provision.ProvisionError, match="METABASE_ADMIN_PASSWORD"):
        provision.Config.from_env({k: v for k, v in ENV.items() if k != "METABASE_ADMIN_PASSWORD"})

    fake = FakeMetabase(set_up=True)
    config = provision.Config.from_env({**ENV, "METABASE_ADMIN_PASSWORD": "wrong"})
    client = httpx.Client(base_url=config.url, transport=httpx.MockTransport(fake.handle))
    with pytest.raises(provision.ProvisionError, match="login"):
        provision.login(client, config)


def test_main_returns_an_error_code_instead_of_raising():
    assert provision.main({}) == 1
