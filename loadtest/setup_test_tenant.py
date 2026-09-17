"""Provision an isolated tenant/project/agent/channel_connection for load testing.

Creates a dedicated ``loadtest`` tenant through the admin API
(``/internal/admin/*``, see README.md section 8) so stress-test traffic never
touches a real tenant's conversations, and points the agent at a
deliberately nonexistent ``langflow_flow_id`` so no request ever reaches a
real LLM (the gateway/Kafka/worker path still runs in full — see
loadtest/README.md for why that's the right boundary for this test).

Usage:
    python loadtest/setup_test_tenant.py \\
        --base-url https://platform.flowsdone.com \\
        --admin-key "$ADMIN_API_KEY"

Prints the created IDs and writes them to ``loadtest/.tenant.json`` so
``cleanup_test_tenant.py`` can tear everything down afterwards.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

STATE_FILE = Path(__file__).parent / ".tenant.json"
INSTANCE_NAME = "loadtest-instance-1"


def create_test_tenant(base_url: str, admin_key: str) -> dict:
    """Create the tenant/project/agent/channel_connection chain for load testing.

    Args:
        base_url: Gateway base URL, e.g. ``https://platform.flowsdone.com``.
        admin_key: Value of ``ADMIN_API_KEY``, sent as ``X-Admin-Api-Key``.

    Returns:
        A dict with the four created ids/slugs, also persisted to
        ``STATE_FILE``.

    Raises:
        httpx.HTTPStatusError: If any admin API call fails (e.g. wrong key,
            or a tenant/slug collision from a previous unfinished run — see
            README.md's cleanup instructions).
    """
    headers = {"X-Admin-Api-Key": admin_key, "Content-Type": "application/json"}
    with httpx.Client(base_url=base_url, headers=headers, timeout=15.0) as client:
        tenant = _post(client, "/internal/admin/tenants", {
            "name": "Load Test", "slug": "loadtest",
        })
        project = _post(client, "/internal/admin/projects", {
            "tenant_id": tenant["id"], "name": "Load Test", "slug": "loadtest",
        })
        agent = _post(client, "/internal/admin/agents", {
            "project_id": project["id"],
            "name": "Load Test Agent",
            "langflow_flow_id": "loadtest-nonexistent-flow",
            "is_default": True,
        })
        channel = _post(client, "/internal/admin/channel-connections", {
            "project_id": project["id"],
            "agent_id": agent["id"],
            "channel_type": "whatsapp_evolution",
            "external_id": INSTANCE_NAME,
            "credentials": {},
        })

    result = {
        "tenant_id": tenant["id"],
        "project_id": project["id"],
        "agent_id": agent["id"],
        "channel_connection_id": channel["id"],
        "instance": INSTANCE_NAME,
        "base_url": base_url,
    }
    STATE_FILE.write_text(json.dumps(result, indent=2))
    return result


def _post(client: httpx.Client, path: str, body: dict) -> dict:
    resp = client.post(path, json=body)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="e.g. https://platform.flowsdone.com")
    parser.add_argument("--admin-key", required=True, help="value of ADMIN_API_KEY")
    args = parser.parse_args()

    try:
        result = create_test_tenant(args.base_url, args.admin_key)
    except httpx.HTTPStatusError as exc:
        print(f"Falló el setup: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        print("Si ya corriste este script antes, corré cleanup_test_tenant.py primero.", file=sys.stderr)
        sys.exit(1)

    print("Tenant de load test creado:")
    print(json.dumps(result, indent=2))
    print(f"\nGuardado en {STATE_FILE} — usalo en cleanup_test_tenant.py al terminar.")
    print(f"\nExportá antes de correr locust:\n  export LOADTEST_INSTANCE={result['instance']}")


if __name__ == "__main__":
    main()
