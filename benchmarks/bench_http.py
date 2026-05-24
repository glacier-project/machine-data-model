"""HTTP exposer benchmarks.

Each scenario builds a fresh DataModel + ExposerManager + aiohttp
ClientSession and drives K concurrent in-flight requests against a
single target node. Per-request latency is measured (network +
executor + JSON), so the percentile fields are meaningful.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import socket
import threading
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from machine_data_model.data_model import DataModel
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.exposers.http_exposer import HttpExposer
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import NumericalVariableNode

if TYPE_CHECKING:
    from benchmarks._harness import Scenario

from benchmarks._harness import Sample


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_data_model() -> tuple[DataModel, NumericalVariableNode, MethodNode]:
    """Build a small data model with one numerical variable + one method.

    The method declares one ``result`` return because MethodNode's
    return-dict builder indexes ``self._returns`` on every callback
    return value.
    """
    temp = NumericalVariableNode(name="Temperature", value=0.0)

    result_node = NumericalVariableNode(name="result", value=0.0)
    method = MethodNode(
        name="Sum",
        returns=[result_node],
        callback=lambda a=0, b=0: a + b,
    )

    sensors = FolderNode(name="Sensors")
    sensors.add_child(temp)
    sensors.add_child(method)
    root = FolderNode(name="root")
    root.add_child(sensors)
    return DataModel(name="bench", root=root), temp, method


class _HttpFixture:
    """Owns the manager and the client loop for HTTP scenarios."""

    manager: ExposerManager
    temp: NumericalVariableNode
    method: MethodNode
    base_url: str
    _client_loop: asyncio.AbstractEventLoop
    _client_thread: threading.Thread

    def start(self) -> None:
        """Spin up the ExposerManager and a dedicated client loop."""
        data_model, temp, method = _build_data_model()
        self.temp = temp
        self.method = method
        port = _find_free_port()
        self.manager = ExposerManager(
            data_model, host="127.0.0.1", port=port
        )
        self.manager.add_exposer(HttpExposer())
        self.manager.start()
        self.base_url = f"http://127.0.0.1:{port}"

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
        """Stop the client loop and the ExposerManager in order."""
        self._client_loop.call_soon_threadsafe(self._client_loop.stop)
        self._client_thread.join(timeout=2.0)
        self._client_loop.close()
        self.manager.stop()

    def submit(self, coro: Any) -> Any:
        """Submit a coroutine to the client loop and wait for the result."""
        return asyncio.run_coroutine_threadsafe(
            coro, self._client_loop
        ).result()


async def _driver_loop(
    session: aiohttp.ClientSession,
    do_one: Any,  # async (session) -> int (latency_ns)
    duration_s: float,
    concurrency: int,
) -> list[int]:
    """Keep ``concurrency`` requests in flight for ``duration_s`` seconds."""
    end = time.monotonic() + duration_s
    latencies: list[int] = []
    in_flight: set[asyncio.Task[int]] = set()

    def _spawn() -> None:
        in_flight.add(asyncio.create_task(do_one(session)))

    for _ in range(concurrency):
        _spawn()

    while time.monotonic() < end:
        done, _ = await asyncio.wait(
            in_flight,
            return_when=asyncio.FIRST_COMPLETED,
            timeout=0.05,
        )
        for t in done:
            in_flight.discard(t)
            with contextlib.suppress(Exception):
                # Drop failed requests from latency stats — matches the
                # drain's isinstance(r, int) guard below.
                latencies.append(t.result())
            if time.monotonic() < end:
                _spawn()

    # Drain remaining in-flight to keep the server consistent on next run.
    if in_flight:
        finished = await asyncio.gather(*in_flight, return_exceptions=True)
        for r in finished:
            if isinstance(r, int):
                latencies.append(r)
    return latencies


@dataclass
class ReadScenario:
    """GET /nodes/Sensors/Temperature with K concurrent clients."""

    name: str = "http.read"
    params: dict[str, Any] = field(
        default_factory=lambda: {"concurrency": 32}
    )
    _fix: _HttpFixture = field(init=False, repr=False)

    def setup(self) -> None:
        """Start the HTTP fixture (manager + client loop)."""
        self._fix = _HttpFixture()
        self._fix.start()

    def run(self, duration_s: float) -> list[Sample]:
        """Drive concurrent GETs against /nodes/Sensors/Temperature."""
        base = self._fix.base_url
        concurrency = int(self.params["concurrency"])

        async def _go() -> list[int]:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async def _do_one(s: aiohttp.ClientSession) -> int:
                    t0 = time.monotonic_ns()
                    async with s.get(f"{base}/nodes/Sensors/Temperature") as r:
                        await r.read()
                    return time.monotonic_ns() - t0

                return await _driver_loop(
                    session, _do_one, duration_s, concurrency
                )

        latencies = self._fix.submit(_go())
        return [Sample(latency_ns=lat) for lat in latencies]

    def teardown(self) -> None:
        """Stop the HTTP fixture."""
        self._fix.stop()


@dataclass
class WriteScenario:
    """POST /nodes/Sensors/Temperature with K concurrent clients."""

    name: str = "http.write"
    params: dict[str, Any] = field(
        default_factory=lambda: {"concurrency": 32}
    )
    _fix: _HttpFixture = field(init=False, repr=False)
    _counter: int = field(init=False, default=0)

    def setup(self) -> None:
        """Start the HTTP fixture and reset the value counter."""
        self._fix = _HttpFixture()
        self._fix.start()
        self._counter = 0

    def run(self, duration_s: float) -> list[Sample]:
        """Drive concurrent POSTs that write monotonically increasing values."""
        base = self._fix.base_url
        concurrency = int(self.params["concurrency"])

        async def _go() -> list[int]:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async def _do_one(s: aiohttp.ClientSession) -> int:
                    self._counter += 1
                    payload = {"value": float(self._counter)}
                    t0 = time.monotonic_ns()
                    async with s.post(
                        f"{base}/nodes/Sensors/Temperature",
                        json=payload,
                    ) as r:
                        await r.read()
                    return time.monotonic_ns() - t0

                return await _driver_loop(
                    session, _do_one, duration_s, concurrency
                )

        latencies = self._fix.submit(_go())
        return [Sample(latency_ns=lat) for lat in latencies]

    def teardown(self) -> None:
        """Stop the HTTP fixture."""
        self._fix.stop()


def register_scenarios() -> list[Scenario]:
    """Return all scenarios defined in this module."""
    return [ReadScenario(), WriteScenario()]
