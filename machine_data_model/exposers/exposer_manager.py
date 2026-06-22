"""ExposerManager - owns the asyncio thread, executor, and aiohttp app."""

import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
import contextlib
import logging
import threading

from aiohttp import web
from aiohttp.typedefs import Middleware

from machine_data_model.data_model import DataModel
from machine_data_model.exposers._coalescer import NodeChangeCoalescer
from machine_data_model.exposers.abstract_exposer import AbstractExposer
from machine_data_model.nodes.data_model_node import DataModelNode

_logger = logging.getLogger(__name__)


class ExposerManager:
    """Bridges a synchronous DataModel to an async network layer."""

    def __init__(
        self,
        data_model: DataModel,
        host: str = "127.0.0.1",
        port: int = 8080,
        event_loop: AbstractEventLoop | None = None,
        middlewares: Iterable[Middleware] | None = None,
    ) -> None:
        """Initialize the manager.

        Args:
            data_model:
                The DataModel this manager exposes.
            host:
                Host the aiohttp server binds to. Defaults to ``127.0.0.1``
                (loopback): the exposer surface has no built-in auth or TLS,
                so binding to other interfaces (e.g. ``0.0.0.0``) is an
                explicit opt-in and should be paired with ``middlewares``
                that add authentication.
            port:
                Port the aiohttp server binds to.
            event_loop:
                Optional pre-existing asyncio event loop. When None
                (the default), a fresh loop is created in a new
                background thread on ``start()`` and torn down on
                ``stop()``.
            middlewares:
                Optional aiohttp middlewares applied to every route. Use
                this to inject authentication/authorization before exposing
                read/write/method-invoke access.
        """
        self._data_model = data_model
        self._host = host
        self._port = port
        self._supplied_event_loop = event_loop
        self._middlewares = list(middlewares) if middlewares is not None else []
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"exposer-{data_model.name}",
        )
        self._exposers: list[AbstractExposer] = []
        self._loop: AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._runner: web.AppRunner | None = None
        self._coalescer: NodeChangeCoalescer | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._started = False
        self._started_event = threading.Event()
        self._start_error: BaseException | None = None

    @property
    def data_model(self) -> DataModel:
        """The DataModel exposed by this manager."""
        return self._data_model

    def resolve(self, path: str) -> DataModelNode | None:
        """Resolve a relative node path against the data model root.

        A leading ``/`` is optional and the root name may be omitted, so
        ``Sensors/Temp`` and ``root/Sensors/Temp`` resolve identically.
        Returns None if no such node exists.
        """
        path = path.lstrip("/")
        root_name = self._data_model.root.name
        if path == root_name or path.startswith(f"{root_name}/"):
            return self._data_model.get_node(path)
        return self._data_model.get_node(f"{root_name}/{path}")

    @property
    def host(self) -> str:
        """Host the aiohttp server binds to."""
        return self._host

    @property
    def port(self) -> int:
        """Port the aiohttp server binds to."""
        return self._port

    @property
    def executor(self) -> ThreadPoolExecutor:
        """The single-worker pool used to dispatch sync-side calls."""
        return self._executor

    @property
    def coalescer(self) -> NodeChangeCoalescer:
        """The NodeChangeCoalescer (available only after start())."""
        if self._coalescer is None:
            raise RuntimeError("ExposerManager not started")
        return self._coalescer

    def add_exposer(self, exposer: AbstractExposer) -> None:
        """Register an exposer; must be called before ``start()``."""
        if self._started:
            raise RuntimeError("Cannot add exposers after start()")
        self._exposers.append(exposer)

    def start(self, timeout: float = 5.0) -> None:
        """Start the asyncio thread and the aiohttp server.

        Args:
            timeout:
                Seconds to wait for the server to come up before raising.
        """
        if self._started:
            raise RuntimeError("ExposerManager already started")
        self._started = True
        if self._supplied_event_loop is not None:
            self._loop = self._supplied_event_loop
            asyncio.run_coroutine_threadsafe(self._serve(), self._loop)
        else:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"exposer-loop-{self._data_model.name}",
                daemon=True,
            )
            self._thread.start()
        if not self._started_event.wait(timeout=timeout):
            self._started = False
            raise RuntimeError("ExposerManager start timed out")
        if self._start_error is not None:
            err = self._start_error
            self._start_error = None
            self._started = False
            raise RuntimeError("ExposerManager start failed") from err

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            self._loop.close()

    async def _serve(self) -> None:
        assert self._loop is not None
        try:
            self._coalescer = NodeChangeCoalescer(self._loop)
            app = web.Application(middlewares=self._middlewares)
            for exposer in self._exposers:
                exposer.register(app, self)
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            site = web.TCPSite(self._runner, self._host, self._port)
            await site.start()
            # Reflect the OS-assigned port back when an ephemeral port (0)
            # was requested, so callers can discover where we bound.
            if self._port == 0 and self._runner.addresses:
                self._port = self._runner.addresses[0][1]
            self._pump_task = asyncio.create_task(self._coalescer.run_pump())
        except BaseException as e:
            self._start_error = e
            # Tear down a partially set-up runner so a failed start (e.g.
            # port in use) does not leak it (F8).
            if self._runner is not None:
                with contextlib.suppress(Exception):
                    await self._runner.cleanup()
                self._runner = None
            self._started_event.set()
            return
        self._started_event.set()
        # Block here until the loop is stopped externally.
        self._shutdown_event = asyncio.Event()
        with contextlib.suppress(asyncio.CancelledError):
            await self._shutdown_event.wait()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the server, drain the pump, and tear down the loop thread."""
        if not self._started:
            return
        assert self._loop is not None

        async def _shutdown() -> None:
            if self._runner is not None:
                await self._runner.cleanup()
            if self._pump_task is not None:
                self._pump_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._pump_task
            if self._shutdown_event is not None:
                self._shutdown_event.set()

        if self._supplied_event_loop is None:
            future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
            try:
                future.result(timeout=timeout)
            except Exception:
                _logger.warning(
                    "ExposerManager shutdown exceeded timeout; forcing"
                )
            if self._thread is not None:
                self._thread.join(timeout=timeout)
                if self._thread.is_alive():
                    _logger.warning(
                        "Exposer loop thread did not exit within timeout"
                    )
        else:
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(
                timeout=timeout
            )
        # cancel_futures drops queued-but-unstarted jobs so a backlog cannot
        # block shutdown; we still wait for the in-flight job to finish.
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._started = False
