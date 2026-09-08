"""Shared pytest configuration for the whole suite.

Async tests use anyio (already a transitive dependency of
fastapi/httpx, so no extra async-test runner is added) with the
asyncio backend only — trio is not used anywhere in this project.
"""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
