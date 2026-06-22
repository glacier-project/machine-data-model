"""Abstract base class for HTTP/WebSocket exposers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import web

    from machine_data_model.exposers.exposer_manager import ExposerManager


class AbstractExposer(ABC):
    """Base class for exposers that publish a DataModel to the network.

    Each concrete subclass attaches its handlers to a shared aiohttp
    Application via ``register``. Implementations may also wire
    themselves into the manager's coalescer to receive node changes.
    """

    @abstractmethod
    def register(
        self,
        app: "web.Application",
        manager: "ExposerManager",
    ) -> None:
        """Attach routes/handlers to the shared aiohttp Application.

        Called once, on the asyncio thread, during
        ``ExposerManager.start()`` and before the server begins
        accepting connections.

        Args:
            app:
                The shared aiohttp Application.
            manager:
                The ExposerManager that owns this exposer.
        """
