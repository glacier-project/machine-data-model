"""Abstract Async Connector.

This module defines the AbstractAsyncConnector abstract class.
It is used to define connectors which use libraries that
follow the async/await programming paradigm.
"""

from abc import abstractmethod
import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
import logging
from threading import Thread
from typing import Any, TypeVar

from typing_extensions import override

from .abstract_connector import AbstractConnector, SubscriptionArguments
from .remote_resource import RemoteResource

TaskReturnType = TypeVar("TaskReturnType")

_logger = logging.getLogger(__name__)


def create_event_loop_thread() -> tuple[AbstractEventLoop, Thread]:
    """Creates a thread with an asyncio event loop.

    The loop can then be used to execute the async tasks inside the thread.

    Credits:
    https://gist.github.com/dmfigol/3e7d5b84a16d076df02baa9f53271058?permalink_comment_id=5553292#gistcomment-5553292

    Returns:
        tuple[AbstractEventLoop, Thread]:
            Asyncio event loop and thread running it.
    """

    def start_background_loop(loop: AbstractEventLoop) -> None:
        """Runs the asyncio loop forever.

        Args:
            loop (AbstractEventLoop):
                The asyncio event loop.
        """
        asyncio.set_event_loop(loop)
        loop.run_forever()

    _logger.debug("Creating thread and its event loop")
    event_loop = asyncio.new_event_loop()
    thread = Thread(
        target=start_background_loop, args=(event_loop,), daemon=True
    )
    thread.start()
    _logger.debug("Created thread and its event loop")
    return event_loop, thread


def run_coroutine_in_thread(
    loop: AbstractEventLoop, coro: Coroutine[None, None, TaskReturnType]
) -> Future[TaskReturnType]:
    """Runs a coroutine in a thread.

    Use create_event_loop_thread() to get the loop.

    Credits:
    https://gist.github.com/dmfigol/3e7d5b84a16d076df02baa9f53271058?permalink_comment_id=5553292#gistcomment-5553292

    Args:
        loop (AbstractEventLoop):
            The asyncio event loop.
        coro (Coroutine[Any, Any, TaskReturnType]):
            The coroutine which needs to be executed in the event loop.

    Returns:
        Future[TaskReturnType]:
            Future which allows to retrieve the result of the coroutine.
    """
    return asyncio.run_coroutine_threadsafe(coro, loop)


class AbstractAsyncConnector(AbstractConnector):
    """Represents a generic asynchronous connector/client."""

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        ip: str | None = None,
        ip_env_var: str | None = None,
        port: int | None = None,
        port_env_var: str | None = None,
        event_loop: AbstractEventLoop | None = None,
        username: str | None = None,
        username_env_var: str | None = None,
        password: str | None = None,
        password_env_var: str | None = None,
    ) -> None:
        """AbstractAsyncConnector constructor.

        Args:
            id (str | None):
                Connector's object id.
            name (str | None):
                Connector's name/identifier
            ip (str | None):
                Server's IP address.
            ip_env_var (str | None):
                Environment variable which contains the server's IP address
            port (int | None):
                Server's port.
            port_env_var (str | None):
                Environment variable which contains the server's port.
            event_loop (AbstractEventLoop | None):
                Event loop which will be used to execute the asynchronous tasks.
            username (str | None):
                Username used to authenticate to the server
            username_env_var (str | None):
                Environment variable which contains the username used to
                authenticate to the server.
            password (str | None):
                Password used to authenticate to the server.
            password_env_var (str | None):
                Environment variable which contains the password used to
                authenticate to the server.
        """
        super().__init__(
            id=id,
            name=name,
            ip=ip,
            ip_env_var=ip_env_var,
            port=port,
            port_env_var=port_env_var,
            username=username,
            username_env_var=username_env_var,
            password=password,
            password_env_var=password_env_var,
        )

        self._owns_event_loop = event_loop is None
        self._event_loop_thread: Thread | None = None
        if event_loop is None:
            self._event_loop, self._event_loop_thread = (
                create_event_loop_thread()
            )
        else:
            self._event_loop = event_loop

    @override
    def connect(self) -> bool:
        """Connects to the remote resource.

        Returns:
            bool:
                True if the client is connected to the server.
        """
        self._ensure_owned_event_loop()
        return self._handle_task(self._async_connect())

    def _ensure_owned_event_loop(self) -> None:
        """Create a fresh private event loop when reconnecting."""
        if not self._owns_event_loop:
            return
        if self._event_loop.is_closed():
            self._event_loop, self._event_loop_thread = (
                create_event_loop_thread()
            )

    @abstractmethod
    async def _async_connect(self) -> bool:
        """Asynchronous code which uses the client to connect to the server.

        Returns:
            bool:
                True if the client is connected to the server.
        """

    @override
    def disconnect(self) -> bool:
        """Disconnect from the remote resource.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """
        if self._event_loop.is_closed():
            return True
        try:
            res = self._handle_task(self._async_disconnect())
        finally:
            self._stop_owned_event_loop()
        return res

    def _stop_owned_event_loop(self) -> None:
        """Stop and close the private event loop when this connector owns it."""
        if not self._owns_event_loop or self._event_loop.is_closed():
            return
        if self._event_loop.is_running():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            if self._event_loop_thread is not None:
                self._event_loop_thread.join(timeout=5)
        if not self._event_loop.is_running():
            self._event_loop.close()

    @abstractmethod
    async def _async_disconnect(self) -> bool:
        """Asynchronously disconnects the client from the remote resource.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """

    @override
    def _get_remote_resource(self, resource: RemoteResource) -> Any:
        """Resolve and return a protocol-specific remote resource handle.

        Args:
            resource:
                Resolved remote resource reference.

        Returns:
            Any:
                Protocol-specific resource handle.
        """
        return self._handle_task(self._async_get_remote_resource(resource))

    @abstractmethod
    async def _async_get_remote_resource(self, resource: RemoteResource) -> Any:
        """Asynchronously resolve a protocol-specific remote resource handle.

        Args:
            resource:
                Resolved remote resource reference.

        Returns:
            Any:
                Protocol-specific resource handle.
        """

    @override
    def read_node_value(self, resource: RemoteResource) -> Any:
        """Retrieve and return a node's value.

        Args:
            resource:
                Resolved remote resource reference.

        Returns:
            Any:
                Node's value.
        """
        return self._handle_task(self._async_read_node_value(resource))

    @abstractmethod
    async def _async_read_node_value(self, resource: RemoteResource) -> Any:
        """Asynchronous code which reads a node's value.

        Args:
            resource:
                Resolved remote resource reference.

        Returns:
            Any:
                Node's value.
        """

    @override
    def write_node_value(
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        """Writes a variable node.

        Args:
            resource:
                Resolved remote resource reference.
            value:
                New value to write.

        Returns:
            bool:
                True if the operation was successful, False otherwise.
        """
        return self._handle_task(self._async_write_node_value(resource, value))

    @abstractmethod
    async def _async_write_node_value(
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        """Asynchronous code which writes a variable node.

        Args:
            resource:
                Resolved remote resource reference.
            value:
                New value to write.

        Returns:
            bool:
                True if the operation was successful, False otherwise.
        """

    @override
    def call_node_as_method(
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        """Invoke the remote method using ``kwargs``.

        Args:
            resource:
                Resolved remote resource reference.
            kwargs:
                Method arguments expressed as key/name - value pairs

        Returns:
            Any:
                Method's returned value.
        """
        return self._handle_task(
            self._async_call_node_as_method(resource, kwargs)
        )

    @abstractmethod
    async def _async_call_node_as_method(
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        """Asynchronously invoke the remote method using ``kwargs``.

        Args:
            resource:
                Resolved remote resource reference.
            kwargs:
                Method arguments expressed as key/name - value pairs.

        Returns:
            Any:
                Method's returned value.
        """

    @override
    def subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        """Subscribes to remote node changes.

        Args:
            resource:
                Resolved remote resource reference.
            callback:
                Subscription's callback. The first parameter is the new value,
                while the second parameter is additional data that is protocol
                dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """
        return self._handle_task(
            self._async_subscribe_to_node_changes(
                resource,
                callback,
            )
        )

    @abstractmethod
    async def _async_subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        """Asynchronously subscribes to remote node changes.

        Args:
            resource:
                Resolved remote resource reference.
            callback:
                Subscription's callback. The first parameter is the new value,
                while the second parameter is additional data that is protocol
                dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """

    def _handle_task(
        self,
        task: Coroutine[None, None, TaskReturnType],
        timeout: float | None = None,
    ) -> TaskReturnType:
        """Run a task in the thread, wait for the result and return it.

        Args:
            task (Coroutine[None, None, TaskReturnType]):
                Coroutine which will be executed in the connector's thread.
            timeout (float | None):
                Maximum number of seconds to wait for the result. If None,
                wait indefinitely.

        Returns:
            TaskReturnType:
                Coroutine result.
        """
        if self._event_loop.is_closed():
            task.close()
            raise RuntimeError(
                f"Cannot run task using '{self.name}' connector: the event "
                "loop is closed"
            )
        _logger.debug(f"Running task {task} using '{self.name}' connector")
        res = run_coroutine_in_thread(self._event_loop, task)
        try:
            output = res.result(timeout=timeout)
        except FutureTimeoutError:
            res.cancel()
            raise
        _logger.debug(
            f"Ran task {task} using '{self.name}' connector. "
            f"Its result is {output!r}"
        )
        return output
