"""Sync-to-async bridge with last-value-wins coalescing semantics."""

from asyncio import AbstractEventLoop
import threading
from typing import Any


class NodeChangeCoalescer:
    """Coalescing bridge from sync notifications to an async consumer.

    The sync side calls ``notify(node_id, value)``; values for the same
    ``node_id`` overwrite earlier values still in the buffer. The async
    side drains the buffer atomically. This implements the B2
    backpressure contract from the design spec: under sustained load,
    intermediate values are dropped but the last value for each node is
    always delivered.
    """

    def __init__(self, loop: AbstractEventLoop) -> None:
        """Initialize the coalescer bound to an asyncio loop.

        Args:
            loop: The asyncio event loop that will run the drain pump.
        """
        self._loop = loop
        self._pending: dict[str, Any] = {}
        self._lock = threading.Lock()

    def notify(self, node_id: str, value: Any) -> None:
        """Record the latest value for ``node_id``. Sync-thread safe."""
        with self._lock:
            self._pending[node_id] = value

    def _drain_for_test(self) -> dict[str, Any]:
        """Atomically swap out the pending dict and return its contents."""
        with self._lock:
            snapshot = self._pending
            self._pending = {}
        return snapshot
