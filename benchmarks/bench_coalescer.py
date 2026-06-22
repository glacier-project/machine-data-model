"""Coalescer microbenchmarks (no aiohttp, no sockets).

These isolate the sync->async bridge cost from any network overhead.
Per-op latency is reported as 0 because timing every notify() call
would add ~100 ns of overhead to a ~1 us operation. Throughput
(ops_per_sec) is the meaningful metric here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import threading
import time
from typing import Any

from benchmarks._harness import Sample, Scenario
from machine_data_model.exposers._coalescer import NodeChangeCoalescer


@dataclass
class NotifyScenario:
    """Measures ``coalescer.notify()`` calls/sec with pump running."""

    name: str = "coalescer.notify"
    params: dict[str, Any] = field(default_factory=dict)
    _loop: asyncio.AbstractEventLoop = field(init=False, repr=False)
    _thread: threading.Thread = field(init=False, repr=False)
    _coalescer: NodeChangeCoalescer = field(init=False, repr=False)
    _pump_task: asyncio.Task[None] = field(init=False, repr=False)

    def setup(self) -> None:
        """Start a background asyncio loop, create the coalescer and pump."""
        loop_ready = threading.Event()
        self._loop = asyncio.new_event_loop()

        def _run_loop() -> None:
            asyncio.set_event_loop(self._loop)
            loop_ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        if not loop_ready.wait(timeout=5.0):
            raise RuntimeError(
                "benchmark event loop did not start within 5 s"
            )

        self._coalescer = NodeChangeCoalescer(self._loop)

        async def _noop_consumer(_snapshot: dict[str, Any]) -> None:
            return None

        self._coalescer.add_consumer(_noop_consumer)

        async def _start_pump() -> None:
            # Drive the coalescer pump the same way ExposerManager does.
            self._pump_task = asyncio.create_task(self._coalescer.run_pump())

        asyncio.run_coroutine_threadsafe(_start_pump(), self._loop).result(
            timeout=2.0
        )

    def run(self, duration_s: float) -> list[Sample]:
        """Call notify() in a tight loop for ``duration_s`` seconds."""
        end = time.monotonic() + duration_s
        count = 0
        notify = self._coalescer.notify  # local for tightest loop
        while time.monotonic() < end:
            notify("node", count)
            count += 1
        # latency_ns=0 — see module docstring.
        return [Sample(latency_ns=0) for _ in range(count)]

    def teardown(self) -> None:
        """Cancel the pump task, stop the loop thread, and close the loop."""
        async def _cancel() -> None:
            self._pump_task.cancel()

        asyncio.run_coroutine_threadsafe(_cancel(), self._loop).result(
            timeout=2.0
        )
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._loop.close()


@dataclass
class DrainScenario:
    """Measures pump dispatches/sec under a sustained notify() flood.

    A background producer thread spams notify() on a rotating set of
    node_ids while the pump dispatches snapshots to a counting consumer.
    Samples count *dispatches* (one per drain cycle), not notifies.
    """

    name: str = "coalescer.drain"
    params: dict[str, Any] = field(default_factory=dict)
    _loop: asyncio.AbstractEventLoop = field(init=False, repr=False)
    _thread: threading.Thread = field(init=False, repr=False)
    _coalescer: NodeChangeCoalescer = field(init=False, repr=False)
    _pump_task: asyncio.Task[None] = field(init=False, repr=False)
    _producer: threading.Thread = field(init=False, repr=False)
    _producer_stop: threading.Event = field(init=False, repr=False)
    _dispatch_count: int = field(init=False, default=0)

    def setup(self) -> None:
        """Start a background asyncio loop, coalescer, pump, and producer."""
        loop_ready = threading.Event()
        self._loop = asyncio.new_event_loop()

        def _run_loop() -> None:
            asyncio.set_event_loop(self._loop)
            loop_ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        if not loop_ready.wait(timeout=5.0):
            raise RuntimeError(
                "benchmark event loop did not start within 5 s"
            )

        self._coalescer = NodeChangeCoalescer(self._loop)
        self._dispatch_count = 0

        async def _counting_consumer(_snapshot: dict[str, Any]) -> None:
            self._dispatch_count += 1

        self._coalescer.add_consumer(_counting_consumer)

        async def _start_pump() -> None:
            self._pump_task = asyncio.create_task(self._coalescer.run_pump())

        asyncio.run_coroutine_threadsafe(_start_pump(), self._loop).result(
            timeout=2.0
        )

        self._producer_stop = threading.Event()

        def _produce() -> None:
            i = 0
            notify = self._coalescer.notify
            while not self._producer_stop.is_set():
                # Rotate over 8 keys so the buffer holds a meaningful set.
                notify(f"node{i % 8}", i)
                i += 1

        self._producer = threading.Thread(target=_produce, daemon=True)
        self._producer.start()

    def run(self, duration_s: float) -> list[Sample]:
        """Sleep for ``duration_s`` and return one Sample per pump dispatch."""
        start_dispatches = self._dispatch_count
        time.sleep(duration_s)
        end_dispatches = self._dispatch_count
        diff = end_dispatches - start_dispatches
        return [Sample(latency_ns=0) for _ in range(diff)]

    def teardown(self) -> None:
        """Stop the producer, cancel the pump task, and close the loop."""
        self._producer_stop.set()
        self._producer.join(timeout=2.0)

        async def _cancel() -> None:
            self._pump_task.cancel()

        asyncio.run_coroutine_threadsafe(_cancel(), self._loop).result(
            timeout=2.0
        )
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._loop.close()


def register_scenarios() -> list[Scenario]:
    """Return all scenarios defined in this module."""
    return [NotifyScenario(), DrainScenario()]
