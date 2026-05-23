"""Sync-to-async bridge with last-value-wins coalescing semantics."""

import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Awaitable, Callable
import logging
import threading
from typing import Any

_logger = logging.getLogger(__name__)

Consumer = Callable[[dict[str, Any]], Awaitable[None]]


class NodeChangeCoalescer:
    """Coalescing bridge from sync notifications to an async consumer.

    The sync side calls ``notify(node_id, value)``; values for the same
    ``node_id`` overwrite earlier values still in the buffer. The async
    side runs a pump that awaits an Event and drains the buffer
    atomically, then dispatches the snapshot to every registered
    consumer.
    """

    def __init__(self, loop: AbstractEventLoop) -> None:
        """Initialize the coalescer bound to an asyncio loop.

        Args:
            loop:
                The asyncio event loop that will run the drain pump and
                schedule the wake-ups.
        """
        self._loop = loop
        self._pending: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._event = asyncio.Event()
        self._consumers: list[Consumer] = []

    def notify(self, node_id: str, value: Any) -> None:
        """Record the latest value for ``node_id`` and wake the pump."""
        with self._lock:
            self._pending[node_id] = value
        self._loop.call_soon_threadsafe(self._event.set)

    def add_consumer(self, consumer: Consumer) -> None:
        """Register an async callback to receive drained snapshots."""
        self._consumers.append(consumer)

    def _drain_for_test(self) -> dict[str, Any]:
        """Atomically swap out the pending dict and return its contents."""
        with self._lock:
            snapshot = self._pending
            self._pending = {}
        return snapshot

    async def _run_pump(self) -> None:
        """Drain forever: wait, swap, dispatch, repeat."""
        while True:
            await self._event.wait()
            with self._lock:
                snapshot = self._pending
                self._pending = {}
                self._event.clear()
            if not snapshot:
                continue
            for consumer in list(self._consumers):
                try:
                    await consumer(snapshot)
                except Exception:
                    _logger.exception(
                        "Exposer coalescer consumer raised; continuing"
                    )
