"""ExposerManager - owns the asyncio thread, executor, and aiohttp app."""

from asyncio import AbstractEventLoop

from machine_data_model.data_model import DataModel


class ExposerManager:
    """Bridges a synchronous DataModel to an async network layer.

    Owns the background asyncio loop and thread, the single-worker
    executor used to dispatch sync-side calls, the aiohttp Application,
    the NodeChangeCoalescer, and the registered exposers.
    """

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
