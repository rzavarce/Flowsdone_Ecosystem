"""Load test for the Flowsdone gateway's WhatsApp webhook ingestion path.

Exercises the real chain described in section 2 of the repo README:
``POST /webhooks/whatsapp`` -> Switchboard -> Kafka (``inbound.messages``) ->
``kafka_inbound_worker``. It deliberately targets a dedicated, isolated
``channel_connection`` (see ``setup_test_tenant.py``) pointing at a
non-existent Langflow flow id, so load-test traffic never reaches a real LLM
and never mixes with real tenant data — see loadtest/README.md for why that
is safe and what it does NOT cover (the Langflow call itself).

Usage (see README.md for the full walkthrough and safety notes):

    pip install -r loadtest/requirements.txt
    LOADTEST_INSTANCE=loadtest-instance-1 \\
    LOADTEST_APIKEY=<EVOLUTION_API_KEY> \\
        locust -f loadtest/locustfile.py --host https://platform.flowsdone.com

Then open http://localhost:8089 and drive the run from the Locust web UI, or
run headless with ``--headless -u <users> -r <spawn-rate> -t <duration>``.

A staged ``LoadTestShape`` is included (``GradualRampShape``) so a headless
run ramps up in controlled steps instead of slamming max load immediately —
opt into it with ``--headless`` (Locust auto-uses the only shape class
defined in the file).
"""

import os

from locust import HttpUser, LoadTestShape, task, between

from payloads import build_whatsapp_webhook_payload

INSTANCE = os.environ.get("LOADTEST_INSTANCE", "loadtest-instance-1")
APIKEY = os.environ.get("LOADTEST_APIKEY", "")

if not APIKEY:
    raise RuntimeError(
        "LOADTEST_APIKEY is not set — source .env.local or .env.vps first "
        "(see loadtest/.env.local.example / .env.vps.example)."
    )


class WhatsAppInboundUser(HttpUser):
    """Simulates one distinct WhatsApp end user sending inbound messages."""

    wait_time = between(1.0, 3.0)

    @task
    def send_message(self):
        """POST one inbound WhatsApp webhook event and record the response."""
        payload = build_whatsapp_webhook_payload(INSTANCE)
        headers = {"apikey": APIKEY, "Content-Type": "application/json"}
        with self.client.post(
            "/webhooks/whatsapp", json=payload, headers=headers, catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"unexpected status {resp.status_code}: {resp.text[:200]}")
            elif resp.json().get("status") not in ("ok", "ignored"):
                resp.failure(f"unexpected body: {resp.text[:200]}")


if os.environ.get("LOADTEST_SHAPE") == "1":
    # Locust ignores -u/-r whenever ANY LoadTestShape subclass is defined in
    # the locustfile, headless or not — so this class only exists when
    # explicitly opted into. Forgetting this cost us a burst test that
    # silently ran at the shape's stage-1 concurrency (5 users) instead of
    # the requested -u 100, and made an earlier "steady 20 users" resilience
    # run actually follow the ramp instead (5 users, then 25) — harmless for
    # that particular test's conclusion, but not what was asked for.
    class GradualRampShape(LoadTestShape):
        """Conservative staged ramp for a full throughput/latency sweep.

        Stays at each concurrency level for a few minutes before stepping up,
        so a human watching the OpenSearch/Langfuse dashboards has time to
        react before the next step. Edit ``STAGES`` to go further once a
        level is confirmed healthy — do not skip straight to the last stage
        on a first run against production (see README.md, "Cómo correrlo con
        seguridad"). Enable with ``LOADTEST_SHAPE=1``; without it, plain
        ``-u``/``-r`` flags control concurrency directly.
        """

        STAGES = [
            {"duration": 120, "users": 5, "spawn_rate": 1},
            {"duration": 300, "users": 25, "spawn_rate": 2},
            {"duration": 300, "users": 75, "spawn_rate": 5},
            {"duration": 300, "users": 150, "spawn_rate": 5},
        ]

        def tick(self):
            run_time = self.get_run_time()
            elapsed = 0
            for stage in self.STAGES:
                elapsed += stage["duration"]
                if run_time < elapsed:
                    return stage["users"], stage["spawn_rate"]
            return None
