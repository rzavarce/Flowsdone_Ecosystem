"""Provision Metabase (idempotent): admin account and data sources.

Run inside the `api` container, which already has httpx and reads `.env`:

    docker compose --profile prod run --rm --no-deps \
        -v ./scripts/metabase:/scripts/metabase api python /scripts/metabase/provision.py

What it does:
1. First run only: completes Metabase's setup with the admin account
   (METABASE_ADMIN_EMAIL / METABASE_ADMIN_PASSWORD), and removes the bundled
   sample database.
2. Connects (or updates) the two data sources, always with read-only users:
   - "Flowsdone · Postgres": gatewaydb, only the `analytics` schema
     (role metabase_reader, see scripts/metabase/init-postgres.sh);
   - "Flowsdone · ClickHouse": the `flowsdone` database (user
     metabase_reader, see scripts/clickhouse/users.d/metabase_reader.xml).
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

POSTGRES_SOURCE = "Flowsdone · Postgres"
CLICKHOUSE_SOURCE = "Flowsdone · ClickHouse"


class ProvisionError(Exception):
    """Metabase refused a step; the message says which one."""


@dataclass(frozen=True)
class Config:
    """What the script needs, read from the environment.

    Attributes:
        url (str): Metabase base URL, as seen from the container.
        admin_email (str): Admin account email.
        admin_password (str): Admin account password.
        postgres_password (str): Password of the Postgres metabase_reader role.
        clickhouse_password (str): Password of the ClickHouse metabase_reader user.
    """

    url: str
    admin_email: str
    admin_password: str
    postgres_password: str
    clickhouse_password: str

    @classmethod
    def from_env(cls, env: Dict[str, str]) -> "Config":
        """Build the config, failing clearly on anything missing.

        Args:
            env (Dict[str, str]): The environment (os.environ).

        Returns:
            Config: The configuration.

        Raises:
            ProvisionError: If a required variable is missing.
        """
        required = {
            "METABASE_ADMIN_EMAIL": "admin_email",
            "METABASE_ADMIN_PASSWORD": "admin_password",
            "METABASE_READER_PASSWORD": "postgres_password",
            "CLICKHOUSE_METABASE_PASSWORD": "clickhouse_password",
        }
        missing = [name for name in required if not env.get(name)]
        if missing:
            raise ProvisionError(f"faltan variables en .env: {', '.join(missing)}")
        values = {field: env[name] for name, field in required.items()}
        return cls(url=env.get("METABASE_INTERNAL_URL", "http://metabase:3000").rstrip("/"), **values)


def source_payloads(config: Config) -> Dict[str, Dict[str, Any]]:
    """The data sources Metabase must have, by name.

    Args:
        config (Config): The configuration.

    Returns:
        Dict[str, Dict[str, Any]]: `POST /api/database` bodies by source name.
    """
    return {
        POSTGRES_SOURCE: {
            "engine": "postgres",
            "name": POSTGRES_SOURCE,
            "details": {
                "host": "postgres",
                "port": 5432,
                "dbname": "gatewaydb",
                "user": "metabase_reader",
                "password": config.postgres_password,
                "ssl": False,
                "schema-filters-type": "inclusion",
                "schema-filters-patterns": "analytics",
            },
        },
        CLICKHOUSE_SOURCE: {
            "engine": "clickhouse",
            "name": CLICKHOUSE_SOURCE,
            "details": {
                "host": "clickhouse",
                "port": 8123,
                "dbname": "flowsdone",
                "user": "metabase_reader",
                "password": config.clickhouse_password,
                "ssl": False,
            },
        },
    }


def wait_until_ready(client: httpx.Client, *, attempts: int = 60, delay: float = 5.0) -> None:
    """Wait for Metabase to answer its health check.

    Args:
        client (httpx.Client): Client pointing at Metabase.
        attempts (int): How many times to try.
        delay (float): Seconds between tries.

    Raises:
        ProvisionError: If it never becomes healthy.
    """
    for _ in range(attempts):
        try:
            if client.get("/api/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(delay)
    raise ProvisionError("Metabase no responde en /api/health")


def ensure_setup(client: httpx.Client, config: Config) -> bool:
    """Complete Metabase's first-run setup with the admin account, if pending.

    Args:
        client (httpx.Client): Client pointing at Metabase.
        config (Config): The configuration.

    Returns:
        bool: True if the setup was done now, False if it was already done.

    Raises:
        ProvisionError: If Metabase refuses the setup.
    """
    properties = client.get("/api/session/properties").json()
    if properties.get("has-user-setup"):
        return False
    response = client.post(
        "/api/setup",
        json={
            "token": properties["setup-token"],
            "user": {
                "email": config.admin_email,
                "password": config.admin_password,
                "first_name": "Flowsdone",
                "last_name": "Admin",
                "site_name": "Flowsdone",
            },
            "prefs": {"site_name": "Flowsdone", "site_locale": "es", "allow_tracking": False},
        },
    )
    if response.status_code != 200:
        raise ProvisionError(f"setup rechazado (HTTP {response.status_code}): {response.text[:300]}")
    return True


def login(client: httpx.Client, config: Config) -> None:
    """Log in as the admin; the session header is set on the client.

    Args:
        client (httpx.Client): Client pointing at Metabase.
        config (Config): The configuration.

    Raises:
        ProvisionError: If the credentials are refused.
    """
    response = client.post("/api/session", json={"username": config.admin_email, "password": config.admin_password})
    if response.status_code != 200:
        raise ProvisionError(f"login rechazado (HTTP {response.status_code}): revisa METABASE_ADMIN_EMAIL/PASSWORD")
    client.headers["X-Metabase-Session"] = response.json()["id"]


def ensure_sources(client: httpx.Client, config: Config) -> Dict[str, int]:
    """Create the data sources that are missing and refresh the others.

    Existing ones get their connection details (e.g. a rotated password)
    updated, so re-running after changing `.env` is enough.

    Args:
        client (httpx.Client): Logged-in client.
        config (Config): The configuration.

    Returns:
        Dict[str, int]: Metabase database id by source name.

    Raises:
        ProvisionError: If Metabase refuses a source (e.g. cannot connect).
    """
    listed = client.get("/api/database").json()
    existing = {db["name"]: db["id"] for db in (listed.get("data", listed) if isinstance(listed, dict) else listed)}
    ids: Dict[str, int] = {}
    for name, payload in source_payloads(config).items():
        if name in existing:
            response = client.put(f"/api/database/{existing[name]}", json=payload)
        else:
            response = client.post("/api/database", json=payload)
        if response.status_code not in (200, 201):
            raise ProvisionError(f"fuente {name!r} rechazada (HTTP {response.status_code}): {response.text[:300]}")
        ids[name] = int(response.json()["id"])
    return ids


def remove_sample_database(client: httpx.Client) -> bool:
    """Delete Metabase's bundled "Sample Database", so only our data shows.

    Args:
        client (httpx.Client): Logged-in client.

    Returns:
        bool: True if it was there and got deleted.
    """
    listed = client.get("/api/database").json()
    for db in listed.get("data", listed) if isinstance(listed, dict) else listed:
        if db.get("is_sample"):
            client.delete(f"/api/database/{db['id']}")
            return True
    return False


def main(env: Optional[Dict[str, str]] = None) -> int:
    """Run the whole provisioning.

    Args:
        env (Optional[Dict[str, str]]): Environment; os.environ by default.

    Returns:
        int: Process exit code.
    """
    try:
        config = Config.from_env(dict(env if env is not None else os.environ))
        with httpx.Client(base_url=config.url, timeout=60.0) as client:
            wait_until_ready(client)
            if ensure_setup(client, config):
                print("metabase: configuración inicial hecha")
            login(client, config)
            if remove_sample_database(client):
                print("metabase: base de ejemplo eliminada")
            for name, db_id in ensure_sources(client, config).items():
                print(f"metabase: fuente {name!r} lista (id {db_id})")
    except ProvisionError as exc:
        print(f"metabase: ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
