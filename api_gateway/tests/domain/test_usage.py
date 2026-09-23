"""Tests for the cost catalog and rating (domain/models/usage.py)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.models.usage import CostCatalog, UsageAggregate
from api_gateway.tests.support.fakes import make_cost_rate

JAN = datetime(2026, 1, 1, tzinfo=timezone.utc)
JUN = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _usage(**overrides) -> UsageAggregate:
    defaults = dict(
        day=date(2026, 7, 1), tenant_id=uuid4(), kind="llm", provider="openai",
        sku="gpt-4.1-mini-2025-04-14", unit="input_token", quantity=Decimal(2_500_000),
    )
    defaults.update(overrides)
    return UsageAggregate(**defaults)


def test_cost_is_quantity_times_price_per_quantity_rounded_to_micros():
    rate = make_cost_rate(price_micros=400_000, per_quantity=1_000_000)  # 0.40 EUR / 1M tokens

    assert rate.cost_micros(Decimal(2_500_000)) == 1_000_000
    assert rate.cost_micros(Decimal(1)) == 0  # 0.4 micros -> 0
    assert rate.cost_micros(Decimal(2)) == 1  # 0.8 micros -> 1


def test_prefix_and_wildcard_patterns_match():
    assert make_cost_rate(sku="gpt-4.1-mini*").matches(kind="llm", provider="openai", sku="gpt-4.1-mini-2025", unit="input_token")
    assert not make_cost_rate(sku="gpt-4.1-mini*").matches(kind="llm", provider="openai", sku="gpt-4.1", unit="input_token")
    assert make_cost_rate(provider="*", sku="*").matches(kind="llm", provider="x", sku="y", unit="input_token")
    assert not make_cost_rate().matches(kind="llm", provider="openai", sku="gpt-4.1-mini", unit="output_token")
    assert not make_cost_rate(kind="channel").matches(kind="llm", provider="openai", sku="gpt-4.1-mini", unit="input_token")


def test_the_most_specific_rate_wins():
    generic = make_cost_rate(provider="*", sku="*", price_micros=1)
    prefix = make_cost_rate(sku="gpt-4.1*", price_micros=2)
    longer_prefix = make_cost_rate(sku="gpt-4.1-mini*", price_micros=3)
    exact = make_cost_rate(sku="gpt-4.1-mini-2025-04-14", price_micros=4)
    catalog = CostCatalog([generic, prefix, longer_prefix, exact])

    found = catalog.find(kind="llm", provider="openai", sku="gpt-4.1-mini-2025-04-14", unit="input_token", at=JUN)
    assert found is exact
    found = catalog.find(kind="llm", provider="openai", sku="gpt-4.1-mini-2026", unit="input_token", at=JUN)
    assert found is longer_prefix
    found = catalog.find(kind="llm", provider="anthropic", sku="claude", unit="input_token", at=JUN)
    assert found is generic


def test_a_new_version_applies_only_from_its_valid_from():
    old = make_cost_rate(price_micros=400_000, valid_from=JAN)
    new = make_cost_rate(price_micros=300_000, valid_from=JUN)
    catalog = CostCatalog([new, old])

    before = catalog.rate(_usage(day=date(2026, 5, 31)))
    after = catalog.rate(_usage(day=date(2026, 6, 1)))

    assert before.rate is old and before.cost_micros == 1_000_000
    assert after.rate is new and after.cost_micros == 750_000


def test_usage_without_a_rate_is_unrated_and_costs_zero():
    rated = CostCatalog([]).rate(_usage())

    assert not rated.rated
    assert rated.cost_micros == 0


def test_a_rate_not_yet_valid_is_ignored():
    future = make_cost_rate(valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc))

    assert not CostCatalog([future]).rate(_usage()).rated
