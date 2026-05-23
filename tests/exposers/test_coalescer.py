"""Tests for the NodeChangeCoalescer bridge primitive."""

import asyncio
import contextlib
import threading
from typing import Any

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


@pytest.mark.exposer
def test_concurrent_notify_does_not_lose_final_value() -> None:
    """Many threads notifying the same key never lose the final value."""
    loop = asyncio.new_event_loop()
    try:
        coalescer = NodeChangeCoalescer(loop)
        n_threads = 32
        per_thread = 1000
        barrier = threading.Barrier(n_threads)

        def worker(thread_id: int) -> None:
            barrier.wait()
            for i in range(per_thread):
                coalescer.notify(f"node-{thread_id}", i)

        threads = [
            threading.Thread(target=worker, args=(t,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snapshot = coalescer._drain_for_test()
        assert len(snapshot) == n_threads
        for thread_id in range(n_threads):
            assert snapshot[f"node-{thread_id}"] == per_thread - 1
    finally:
        loop.close()


@pytest.mark.exposer
def test_pump_dispatches_to_registered_consumer() -> None:
    """A registered consumer receives drained snapshots when the pump runs."""
    loop = asyncio.new_event_loop()
    received: list[dict[str, Any]] = []

    async def consumer(snapshot: dict[str, Any]) -> None:
        received.append(snapshot)

    async def driver() -> None:
        coalescer = NodeChangeCoalescer(loop)
        coalescer.add_consumer(consumer)
        pump_task = asyncio.create_task(coalescer._run_pump())
        coalescer.notify("a", 1)
        coalescer.notify("b", 2)
        # Yield until the pump has drained.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if received:
                break
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task

    try:
        loop.run_until_complete(driver())
    finally:
        loop.close()

    assert received == [{"a": 1, "b": 2}]
