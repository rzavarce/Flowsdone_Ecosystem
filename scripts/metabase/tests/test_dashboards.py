"""Integrity tests for the dashboards defined as code (scripts/metabase/dashboards.py).

Run: pytest scripts/metabase/tests
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dashboards as specs  # noqa: E402
import provision  # noqa: E402

ANALYTICS_VIEWS = {"tenants", "projects", "agents", "channel_connections", "conversations", "users", "plans",
                   "subscriptions", "usage_statements", "session_events"}


def test_every_dashboard_item_is_a_known_card_and_fits_the_grid():
    for dashboard in specs.DASHBOARDS:
        placed = specs.layout(dashboard.items)
        for key, heading, row, col, width, height in placed:
            assert (key in specs.CARDS) if key else bool(heading)
            assert 0 <= col and col + width <= 24 and width > 0 and height > 0
        # No two items overlap.
        cells = set()
        for _, _, row, col, width, height in placed:
            block = {(r, c) for r in range(row, row + height) for c in range(col, col + width)}
            assert not cells & block, dashboard.key
            cells |= block


def test_every_card_filters_by_tenant_on_an_allowed_source():
    for key, card in specs.CARDS.items():
        assert "tenant" in card.tags, key
        assert "{{tenant}}" in card.sql, key
        for tag, ref in card.tags.items():
            assert "{{" + tag + "}}" in card.sql, (key, tag)
            schema, table, _column = ref.split(".")
            if card.source == specs.CH:
                assert schema == "flowsdone" and table in {"messages", "usage_events"}, key
            else:
                assert schema == "analytics" and table in ANALYTICS_VIEWS, key
        # Postgres cards only read the analytics schema (never public.*).
        if card.source == specs.PG:
            assert not re.search(r"\bpublic\.", card.sql), key


def test_money_is_only_on_the_admin_dashboard():
    money = {"monthly_fees", "monthly_statements", "clients_by_plan"}
    by_key = {d.key: {i[0] for i in d.items if not isinstance(i, str)} for d in specs.DASHBOARDS}
    assert money <= by_key["platform_admin"]
    assert not money & by_key["platform"] and not money & by_key["client"]


def test_dashcards_map_both_filters_and_the_tenant_is_locked_for_embedding():
    card_ids = {key: n for n, key in enumerate(specs.CARDS, start=1)}
    for dashboard in specs.DASHBOARDS:
        for dashcard in provision.dashcards(dashboard, card_ids):
            if dashcard["card_id"] is None:
                assert dashcard["visualization_settings"]["virtual_card"]["display"] == "heading"
                continue
            mapped = {m["parameter_id"] for m in dashcard["parameter_mappings"]}
            assert "tenant" in mapped
    assert specs.EMBEDDING_PARAMS == {"tenant": "locked", "fecha": "enabled"}
    assert {p["slug"] for p in specs.PARAMETERS} == {"tenant", "fecha"}


@pytest.mark.parametrize("key", ["platform", "platform_admin", "client"])
def test_dashboards_the_gateway_asks_for_exist(key):
    assert key in {d.key for d in specs.DASHBOARDS}
