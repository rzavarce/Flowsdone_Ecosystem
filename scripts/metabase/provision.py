"""Provision Metabase (idempotent): admin account, data sources and dashboards.

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
3. Creates or updates the console's dashboards (scripts/metabase/dashboards.py)
   in their own collection, with static embedding on and the tenant filter
   locked. Cards and dashboards keep their ids across runs.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dashboards as specs  # noqa: E402

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


# Spanish number and date formats (1.593,5 - 26 agosto, 2026) for every chart.
FORMATTING = {
    "type/Number": {"number_separators": ",."},
    "type/Temporal": {"date_style": "D MMMM, YYYY", "date_abbreviate": True},
    "type/Currency": {"currency": "EUR", "currency_style": "symbol"},
}


def ensure_formatting(client: httpx.Client) -> None:
    """Set Metabase's global number/date/currency formatting (Spanish, EUR).

    Args:
        client (httpx.Client): Logged-in client.

    Raises:
        ProvisionError: If Metabase refuses the setting.
    """
    _check(client.put("/api/setting/custom-formatting", json={"value": FORMATTING}), "formato de números")


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


def _items(response: httpx.Response) -> list:
    """Metabase lists come either bare or wrapped in {"data": [...]}.

    Args:
        response (httpx.Response): A list response.

    Returns:
        list: The items.
    """
    body = response.json()
    return body.get("data", []) if isinstance(body, dict) else body


def _check(response: httpx.Response, what: str) -> dict:
    """Fail clearly unless Metabase accepted the request.

    Args:
        response (httpx.Response): The response.
        what (str): What was being done.

    Returns:
        dict: The JSON body.

    Raises:
        ProvisionError: If the status is not 2xx.
    """
    if response.status_code >= 300:
        raise ProvisionError(f"{what} rechazado (HTTP {response.status_code}): {response.text[:300]}")
    return response.json() if response.content else {}


def ensure_collection(client: httpx.Client) -> int:
    """The collection that holds the managed dashboards.

    Args:
        client (httpx.Client): Logged-in client.

    Returns:
        int: Its id.
    """
    for collection in _items(client.get("/api/collection")):
        if collection.get("name") == specs.COLLECTION and not collection.get("archived"):
            return int(collection["id"])
    body = {"name": specs.COLLECTION, "description": specs.COLLECTION_DESCRIPTION}
    return int(_check(client.post("/api/collection", json=body), "colección")["id"])


def field_ids(client: httpx.Client, database_ids: Dict[str, int]) -> Dict[str, int]:
    """Field ids by "schema.table.column" across both sources.

    Args:
        client (httpx.Client): Logged-in client.
        database_ids (Dict[str, int]): Source name -> database id.

    Returns:
        Dict[str, int]: Field ids.
    """
    fields: Dict[str, int] = {}
    for db_id in database_ids.values():
        metadata = _check(client.get(f"/api/database/{db_id}/metadata"), "metadatos")
        for table in metadata.get("tables", []):
            for column in table.get("fields", []):
                fields[f"{table.get('schema') or ''}.{table['name']}.{column['name']}"] = column["id"]
    return fields


def sync_until_fields(client: httpx.Client, database_ids: Dict[str, int], needed: List[str],
                      *, attempts: int = 30, delay: float = 5.0) -> Dict[str, int]:
    """Wait until Metabase has synced the fields the cards filter on.

    A freshly connected source is scanned in the background; the field
    filters need those field ids.

    Args:
        client (httpx.Client): Logged-in client.
        database_ids (Dict[str, int]): Source name -> database id.
        needed (List[str]): "schema.table.column" references.
        attempts (int): How many times to check.
        delay (float): Seconds between checks.

    Returns:
        Dict[str, int]: Field ids.

    Raises:
        ProvisionError: If some field never shows up.
    """
    for attempt in range(attempts):
        fields = field_ids(client, database_ids)
        missing = [ref for ref in needed if ref not in fields]
        if not missing:
            return fields
        if attempt == 0:
            for db_id in database_ids.values():
                client.post(f"/api/database/{db_id}/sync_schema")
        time.sleep(delay)
    raise ProvisionError(f"Metabase no ve estos campos (¿falta la migración 0013?): {', '.join(missing)}")


def card_payload(card: "specs.Card", database_id: int, fields: Dict[str, int], collection_id: int) -> dict:
    """`POST/PUT /api/card` body for a card spec.

    Args:
        card (specs.Card): The spec.
        database_id (int): Its source's database id.
        fields (Dict[str, int]): Field ids.
        collection_id (int): The managed collection.

    Returns:
        dict: The body.
    """
    widgets = {"tenant": "string/=", "fecha": "date/all-options"}
    tags = {
        tag: {
            "id": tag, "name": tag, "display-name": tag.capitalize(), "type": "dimension",
            "dimension": ["field", fields[ref], None], "widget-type": widgets[tag],
        }
        for tag, ref in card.tags.items()
    }
    return {
        "name": card.name,
        "collection_id": collection_id,
        "display": card.display,
        "visualization_settings": card.settings,
        "dataset_query": {"type": "native", "database": database_id,
                          "native": {"query": card.sql, "template-tags": tags}},
    }


def ensure_cards(client: httpx.Client, collection_id: int, database_ids: Dict[str, int],
                 fields: Dict[str, int]) -> Dict[str, int]:
    """Create or update every card, keeping existing ids.

    Args:
        client (httpx.Client): Logged-in client.
        collection_id (int): The managed collection.
        database_ids (Dict[str, int]): Source name -> database id.
        fields (Dict[str, int]): Field ids.

    Returns:
        Dict[str, int]: Card id by card key.
    """
    source_db = {specs.CH: database_ids[CLICKHOUSE_SOURCE], specs.PG: database_ids[POSTGRES_SOURCE]}
    existing = {
        item["name"]: item["id"]
        for item in _items(client.get(f"/api/collection/{collection_id}/items", params={"models": "card"}))
    }
    ids: Dict[str, int] = {}
    for key, card in specs.CARDS.items():
        body = card_payload(card, source_db[card.source], fields, collection_id)
        if card.name in existing:
            ids[key] = int(_check(client.put(f"/api/card/{existing[card.name]}", json=body), f"pregunta {card.name!r}")["id"])
        else:
            ids[key] = int(_check(client.post("/api/card", json=body), f"pregunta {card.name!r}")["id"])
    return ids


def dashcards(dashboard: "specs.Dashboard", card_ids: Dict[str, int]) -> list:
    """The dashboard's cards and headings, with their filter mappings.

    Args:
        dashboard (specs.Dashboard): The spec.
        card_ids (Dict[str, int]): Card id by key.

    Returns:
        list: `dashcards` for `PUT /api/dashboard/:id` (new ids are negative).
    """
    result = []
    for n, (key, heading, row, col, width, height) in enumerate(specs.layout(dashboard.items), start=1):
        base = {"id": -n, "row": row, "col": col, "size_x": width, "size_y": height}
        if key is None:
            result.append({**base, "card_id": None, "parameter_mappings": [], "visualization_settings": {
                "virtual_card": {"name": None, "display": "heading", "visualization_settings": {},
                                 "dataset_query": {}, "archived": False},
                "text": heading, "dashcard.background": False,
            }})
            continue
        card_id = card_ids[key]
        mappings = [
            {"parameter_id": tag, "card_id": card_id, "target": ["dimension", ["template-tag", tag]]}
            for tag in specs.CARDS[key].tags
        ]
        result.append({**base, "card_id": card_id, "parameter_mappings": mappings, "visualization_settings": {}})
    return result


def ensure_dashboards(client: httpx.Client, collection_id: int, card_ids: Dict[str, int]) -> Dict[str, int]:
    """Create or update every dashboard, keeping existing ids.

    Args:
        client (httpx.Client): Logged-in client.
        collection_id (int): The managed collection.
        card_ids (Dict[str, int]): Card id by key.

    Returns:
        Dict[str, int]: Dashboard id by dashboard key.
    """
    existing = {}
    for item in _items(client.get(f"/api/collection/{collection_id}/items", params={"models": "dashboard"})):
        for spec in specs.DASHBOARDS:
            if spec.marker in (item.get("description") or ""):
                existing[spec.key] = item["id"]
    ids: Dict[str, int] = {}
    for spec in specs.DASHBOARDS:
        description = f"{spec.description} {spec.marker}"
        if spec.key in existing:
            dashboard_id = existing[spec.key]
        else:
            created = client.post("/api/dashboard", json={
                "name": spec.name, "description": description, "collection_id": collection_id,
                "parameters": specs.PARAMETERS,
            })
            dashboard_id = int(_check(created, f"dashboard {spec.name!r}")["id"])
        _check(client.put(f"/api/dashboard/{dashboard_id}", json={
            "name": spec.name, "description": description, "collection_id": collection_id,
            "parameters": specs.PARAMETERS, "enable_embedding": True,
            "embedding_params": specs.EMBEDDING_PARAMS, "width": "full",
            "dashcards": dashcards(spec, card_ids),
        }), f"dashboard {spec.name!r}")
        ids[spec.key] = dashboard_id
    return ids


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
            ensure_formatting(client)
            database_ids = ensure_sources(client, config)
            for name, db_id in database_ids.items():
                print(f"metabase: fuente {name!r} lista (id {db_id})")
            needed = sorted({ref for card in specs.CARDS.values() for ref in card.tags.values()})
            fields = sync_until_fields(client, database_ids, needed)
            collection_id = ensure_collection(client)
            card_ids = ensure_cards(client, collection_id, database_ids, fields)
            for key, dashboard_id in ensure_dashboards(client, collection_id, card_ids).items():
                print(f"metabase: dashboard {key!r} listo (id {dashboard_id}, {len(card_ids)} preguntas)")
    except ProvisionError as exc:
        print(f"metabase: ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
