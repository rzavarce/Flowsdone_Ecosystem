"""Tests for OpenTelemetry trace setup (core/tracing.py)."""

from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import settings
from app.core.tracing import instrument_fastapi_app, setup_tracing


def test_setup_tracing_noop_when_otel_disabled(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", False)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")

    setup_tracing()  # must not raise


def test_setup_tracing_noop_when_endpoint_missing(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)

    setup_tracing()  # must not raise


def test_setup_tracing_registers_a_real_tracer_provider(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
    monkeypatch.setattr(settings, "OTEL_SERVICE_NAME", "test-service")

    setup_tracing()

    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_instrument_fastapi_app_noop_when_otel_disabled(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", False)

    instrument_fastapi_app(FastAPI())  # must not raise


def test_instrument_fastapi_app_adds_middleware_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")

    app = FastAPI()
    instrument_fastapi_app(app)

    assert app._is_instrumented_by_opentelemetry is True
