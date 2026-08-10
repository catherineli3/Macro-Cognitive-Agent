"""(Smoke) Verify the Sprint 1 test infrastructure works."""
import pytest


def test_trivial() -> None:
    """Guarantee the test runner functions."""
    assert True


def test_python_version() -> None:
    """Sprint 1 requires Python >= 3.9."""
    import sys

    assert sys.version_info >= (3, 9), f"Expected 3.9+, got {sys.version_info}"
