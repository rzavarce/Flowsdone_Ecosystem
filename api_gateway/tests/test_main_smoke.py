"""Smoke test: the gateway app builds and mounts its key routes (without
running the lifespan, so no broker or database is needed)."""

from __future__ import annotations


def test_the_app_builds_with_its_key_routes():
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes} | set(app.openapi()["paths"])
    assert {"/health", "/ready", "/webhooks/generic"} <= paths
    assert any(p.startswith("/internal/admin/contacts") for p in paths)
    # Outside production the API docs stay available for development.
    assert app.docs_url == "/docs"
