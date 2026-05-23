"""Tests for the NodeChangeCoalescer bridge primitive."""

import asyncio

import pytest

from machine_data_model.exposers._coalescer import NodeChangeCoalescer


@pytest.mark.exposer
def test_single_notify_then_drain_returns_value() -> None:
    """A single notify is surfaced in the next drain."""
    loop = asyncio.new_event_loop()
    try:
        coalescer = NodeChangeCoalescer(loop)
        coalescer.notify("Sensors/Temperature", 25.0)
        snapshot = coalescer._drain_for_test()
        assert snapshot == {"Sensors/Temperature": 25.0}
    finally:
        loop.close()
