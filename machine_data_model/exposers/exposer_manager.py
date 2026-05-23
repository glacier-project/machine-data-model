"""ExposerManager - owns the asyncio thread, executor, and aiohttp app."""

import asyncio
from asyncio import AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor
import contextlib
import logging
import threading

from aiohttp import web

from machine_data_model.data_model import DataModel
from machine_data_model.exposers._coalescer import NodeChangeCoalescer
from machine_data_model.exposers.abstract_exposer import AbstractExposer

_logger = logging.getLogger(__name__)


class ExposerManager:
    """Bridges a synchronous DataModel to an async network layer."""

    def __init__(
        self,
        data_model: DataModel,
        host: str = "0.0.0.0",
        port: int = 8080,
        event_loop: AbstractEventLoop | None = None,
    ) -> None:
        """Initialize the manager.

        Args:
            data_model:
                The DataModel this manager exposes.
            host:
                Host the aiohttp server binds to.
            port:
                Port the aiohttp server binds to.
            event_loop:
                Optional pre-existing asyncio event loop. When None
                (the default), a fresh loop is created in a new
                background thread on ``start()`` and torn down on
                ``stop()``.
        """
        self._data_model = data_model
        self._host = host
        self._port = port
        self._supplied_event_loop = event_loop
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

    def start(self) -> None:
        """Start the asyncio thread and the aiohttp server."""
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
        if not self._started_event.wait(timeout=5.0):
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
            app = web.Application()
            for exposer in self._exposers:
                exposer.register(app, self)
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            site = web.TCPSite(self._runner, self._host, self._port)
            await site.start()
            self._pump_task = asyncio.create_task(self._coalescer._run_pump())
        except BaseException as e:
            self._start_error = e
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
        self._executor.shutdown(wait=True)
        self._started = False
