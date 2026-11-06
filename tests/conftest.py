"""Shared pytest configuration."""

from collections.abc import Iterator

import pytest

from machine_data_model.behavior.control_flow import ControlFlow


@pytest.fixture(autouse=True)
def strict_control_flow(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make control flows strict by default in tests.

    An unexpected exception in a node then fails the test with its traceback
    instead of being turned into an error result. Tests that exercise the
    conversion pass `strict=False` explicitly.
    """
    monkeypatch.setattr(ControlFlow, "default_strict", True)
    yield
