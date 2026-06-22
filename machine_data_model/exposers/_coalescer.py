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
        self._post_close_warned = False

    def notify(self, node_id: str, value: Any) -> None:
        """Record the latest value for ``node_id`` and wake the pump.

        If the asyncio loop has been closed (e.g. during shutdown), the
        wake-up is silently dropped and a single warning is logged for
        the lifetime of this coalescer.
        """
        with self._lock:
            self._pending[node_id] = value
        try:
            self._loop.call_soon_threadsafe(self._event.set)
        except RuntimeError:
            if not self._post_close_warned:
                self._post_close_warned = True
                _logger.warning(
                    "Coalescer notify ignored: asyncio loop is closed"
                )

    def add_consumer(self, consumer: Consumer) -> None:
        """Register an async callback to receive drained snapshots."""
        self._consumers.append(consumer)

    def drain(self) -> dict[str, Any]:
        """Atomically remove and return all pending values.

        Also clears the wake-up event so the pump only re-fires on the next
        ``notify``. Used by the pump and exposed for direct draining/tests.
        """
        with self._lock:
            snapshot = self._pending
            self._pending = {}
            self._event.clear()
        return snapshot

    async def run_pump(self) -> None:
        """Drain forever: wait, drain, dispatch, repeat."""
        while True:
            await self._event.wait()
            snapshot = self.drain()
            if not snapshot:
                continue
            for consumer in list(self._consumers):
                try:
                    await consumer(snapshot)
                except Exception:
                    _logger.exception(
                        "Exposer coalescer consumer raised; continuing"
                    )
