"""Integration test conftest — no DB setup needed for integration tests.

Overrides the root conftest's session-scoped DB fixture to a no-op,
since integration tests use in-memory schemas and mock data.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_tables():
    """No-op: Integration tests don't require database tables."""
    pass
