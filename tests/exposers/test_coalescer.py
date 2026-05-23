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


@pytest.mark.exposer
def test_repeated_notify_same_key_keeps_latest() -> None:
    """Multiple notify calls for the same key collapse to the last value."""
    loop = asyncio.new_event_loop()
    try:
        coalescer = NodeChangeCoalescer(loop)
        coalescer.notify("Sensors/Temperature", 25.0)
        coalescer.notify("Sensors/Temperature", 26.0)
        coalescer.notify("Sensors/Temperature", 27.0)
        snapshot = coalescer._drain_for_test()
        assert snapshot == {"Sensors/Temperature": 27.0}
    finally:
        loop.close()


@pytest.mark.exposer
def test_multiple_keys_all_surfaced() -> None:
    """Notifications for different keys are all returned in one drain."""
    loop = asyncio.new_event_loop()
    try:
        coalescer = NodeChangeCoalescer(loop)
        coalescer.notify("a", 1)
        coalescer.notify("b", 2)
        coalescer.notify("c", 3)
        snapshot = coalescer._drain_for_test()
        assert snapshot == {"a": 1, "b": 2, "c": 3}
    finally:
        loop.close()


@pytest.mark.exposer
def test_drain_empties_buffer() -> None:
    """A second drain after the first returns an empty dict."""
    loop = asyncio.new_event_loop()
    try:
        coalescer = NodeChangeCoalescer(loop)
        coalescer.notify("a", 1)
        coalescer._drain_for_test()
        assert coalescer._drain_for_test() == {}
    finally:
        loop.close()
