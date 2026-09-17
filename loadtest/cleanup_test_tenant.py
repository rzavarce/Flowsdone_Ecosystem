"""Tear down the tenant/project/agent/channel_connection created for load testing.

Reads the ids saved by ``setup_test_tenant.py`` (``loadtest/.tenant.json``)
and deletes them in reverse dependency order (channel_connection -> agent ->
project -> tenant), since cascade-on-delete at the DB level is not something
this script should assume.

Usage:
    python loadtest/cleanup_test_tenant.py --admin-key "$ADMIN_API_KEY"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

STATE_FILE = Path(__file__).parent / ".tenant.json"


def cleanup_test_tenant(admin_key: str) -> None:
    """Delete every object recorded in ``STATE_FILE``, then remove the file.

    Args:
        admin_key: Value of ``ADMIN_API_KEY``, sent as ``X-Admin-Api-Key``.

    Raises:
        FileNotFoundError: If ``setup_test_tenant.py`` was never run (or its
            state file was already cleaned up).
    """
    if not STATE_FILE.exists():
        raise FileNotFoundError(
            f"{STATE_FILE} no existe — no hay nada que limpiar, o ya se corrió cleanup."
        )
    state = json.loads(STATE_FILE.read_text())
    headers = {"X-Admin-Api-Key": admin_key}

    with httpx.Client(base_url=state["base_url"], headers=headers, timeout=15.0) as client:
        _delete(client, f"/internal/admin/channel-connections/{state['channel_connection_id']}")
        _delete(client, f"/internal/admin/agents/{state['agent_id']}")
        _delete(client, f"/internal/admin/projects/{state['project_id']}")
        _delete(client, f"/internal/admin/tenants/{state['tenant_id']}")

    STATE_FILE.unlink()


def _delete(client: httpx.Client, path: str) -> None:
    resp = client.delete(path)
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-key", required=True, help="value of ADMIN_API_KEY")
    args = parser.parse_args()

    try:
        cleanup_test_tenant(args.admin_key)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        print(f"Falló la limpieza: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)

    print("Tenant de load test eliminado correctamente.")


if __name__ == "__main__":
    main()
