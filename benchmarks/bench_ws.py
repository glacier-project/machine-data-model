"""WebSocket exposer benchmarks: fan-out throughput and e2e latency."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import socket
import threading
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from benchmarks._harness import Sample
from machine_data_model.data_model import DataModel
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.exposers.websocket_exposer import WebSocketExposer
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import NumericalVariableNode

if TYPE_CHECKING:
    from benchmarks._harness import Scenario


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _WsFixture:
    """Owns the manager and the client loop for WS scenarios."""

    NODE_PATH = "Sensors/Temperature"

    manager: ExposerManager
    temp: NumericalVariableNode
    ws_url: str
    _client_loop: asyncio.AbstractEventLoop
    _client_thread: threading.Thread

    def start(self) -> None:
        """Build the data model, start ExposerManager, start client loop."""
        temp = NumericalVariableNode(name="Temperature", value=0.0)
        sensors = FolderNode(name="Sensors")
        sensors.add_child(temp)
        root = FolderNode(name="root")
        root.add_child(sensors)
        data_model = DataModel(name="bench-ws", root=root)
        self.temp = temp

        port = _find_free_port()
        self.manager = ExposerManager(
            data_model, host="127.0.0.1", port=port
        )
        self.manager.add_exposer(WebSocketExposer())
        self.manager.start()
        self.ws_url = f"http://127.0.0.1:{port}/ws"

        try:
            loop_ready = threading.Event()
            self._client_loop = asyncio.new_event_loop()

            def _run() -> None:
                asyncio.set_event_loop(self._client_loop)
                loop_ready.set()
                self._client_loop.run_forever()

            self._client_thread = threading.Thread(target=_run, daemon=True)
            self._client_thread.start()
            if not loop_ready.wait(timeout=5.0):
                raise RuntimeError(
                    "benchmark client loop did not start within 5 s"
                )
        except BaseException:
            self.manager.stop()
            raise

    def stop(self) -> None:
        """Stop the client loop, join thread, close loop, stop manager."""
        self._client_loop.call_soon_threadsafe(self._client_loop.stop)
        self._client_thread.join(timeout=2.0)
        self._client_loop.close()
        self.manager.stop()

    def submit(self, coro: Any) -> Any:
        """Submit a coroutine to the client loop and wait for the result."""
        return asyncio.run_coroutine_threadsafe(
            coro, self._client_loop
        ).result()


@dataclass
class FanoutScenario:
    """1 writer floods one node; N WS clients count frames received.

    Reports total frames received across all subscribers as ops_per_sec.
    latency_ns is 0 because per-frame timing would dominate cost — this
    scenario measures throughput, not latency.
    """

    name: str = "ws.fanout"
    params: dict[str, Any] = field(
        default_factory=lambda: {"subscribers": 100}
    )
    _fix: _WsFixture = field(init=False, repr=False)

    def setup(self) -> None:
        """Start the WS fixture."""
        self._fix = _WsFixture()
        self._fix.start()

    def run(self, duration_s: float) -> list[Sample]:
        """Spawn N subscribers, flood the node with writes, sum frames."""
        n_subs = int(self.params["subscribers"])
        url = self._fix.ws_url
        temp = self._fix.temp

        # Per-subscriber counters live OUTSIDE the coroutines so that
        # cancelling a subscriber does not lose its accumulated count.
        counters = [0] * n_subs

        async def _subscriber(
            session: aiohttp.ClientSession, idx: int
        ) -> None:
            async with session.ws_connect(url) as ws:
                await ws.send_json(
                    {"op": "subscribe", "node": self._fix.NODE_PATH}
                )
                await ws.receive_json(timeout=2.0)  # "subscribed" ack
                try:
                    while True:
                        msg = await ws.receive(timeout=duration_s + 2.0)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            break
                        counters[idx] += 1
                except (TimeoutError, asyncio.CancelledError):
                    return

        async def _go() -> int:
            timeout = aiohttp.ClientTimeout(total=duration_s + 10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                sub_tasks = [
                    asyncio.create_task(_subscriber(session, i))
                    for i in range(n_subs)
                ]
                # Give the server a moment to install all subscriptions
                # before the writer starts.
                await asyncio.sleep(0.2)

                # Writer runs on the client loop. temp.write() is a sync
                # call; the coalescer hops the notification to the server
                # loop via call_soon_threadsafe, so this does not block.
                end = time.monotonic() + duration_s
                i = 0
                while time.monotonic() < end:
                    temp.write(float(i))
                    i += 1
                    # Yield so subscribers can drain incoming frames.
                    await asyncio.sleep(0)

                # Cancel and gather. Counts survive because counters[]
                # is captured by closure, not returned from each task.
                for t in sub_tasks:
                    t.cancel()
                await asyncio.gather(*sub_tasks, return_exceptions=True)
                return sum(counters)

        total_frames = self._fix.submit(_go())
        return [Sample(latency_ns=0) for _ in range(total_frames)]

    def teardown(self) -> None:
        """Stop the WS fixture."""
        self._fix.stop()


def register_scenarios() -> list[Scenario]:
    """Return all scenarios defined in this module."""
    return [FanoutScenario()]
