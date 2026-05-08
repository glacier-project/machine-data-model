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
import logging
from threading import Thread
from typing import Any, TypeVar

from typing_extensions import override

from machine_data_model.nodes.connectors.abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)

from .abstract_connector import AbstractConnector, SubscriptionArguments

TaskReturnType = TypeVar("TaskReturnType")

_logger = logging.getLogger(__name__)


def create_event_loop_thread() -> AbstractEventLoop:
    """Creates a thread with an asyncio event loop.

    The loop can then be used to execute the async tasks inside the thread.

    Credits:
    https://gist.github.com/dmfigol/3e7d5b84a16d076df02baa9f53271058?permalink_comment_id=5553292#gistcomment-5553292

    Returns:
        AbstractEventLoop:
            Asyncio event loop which will be run in a separate thread.
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
    return event_loop


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

        self._event_loop = (
            create_event_loop_thread() if event_loop is None else event_loop
        )

    @override
    def connect(self) -> bool:
        """Connects to the remote resource.

        Returns:
            bool:
                True if the client is connected to the server.
        """
        return self._handle_task(self._async_connect())

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
        res = self._handle_task(self._async_disconnect())
        self._event_loop.stop()
        return res

    @abstractmethod
    async def _async_disconnect(self) -> bool:
        """Asynchronously disconnects the client from the remote resource.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """

    @override
    def _get_remote_node(
        self,
        path: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> Any:
        """Retrieves and returns a node from the remote resource.

        Args:
            path (str):
                Node's path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                Node with the given path.
        """
        return self._handle_task(
            self._async_get_remote_node(path, remote_resource_spec)
        )

    @abstractmethod
    async def _async_get_remote_node(
        self,
        path: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> Any:
        """Asynchronously retrieves and returns a node from the remote resource.

        Args:
            path (str):
                Node's path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                Node with the given path.
        """

    @override
    def read_node_value(
        self,
        path: str,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> Any:
        """Reatrieves and returns a node's value.

        Args:
            path (str):
                Node's path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                Node's value.
        """
        return self._handle_task(
            self._async_read_node_value(path, remote_resource_spec)
        )

    @abstractmethod
    async def _async_read_node_value(
        self, path: str, remote_resource_spec: AbstractRemoteResourceSpec | None
    ) -> Any:
        """Asynchronous code which reads a node's value.

        Args:
            path (str):
                Node's path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                Node's value.
        """

    @override
    def write_node_value(
        self,
        path: str,
        value: Any,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> bool:
        """Writes a variable node.

        Args:
            path (str):
                Node's path.
            value (Any):
                New value to write.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            bool:
                True if the operation was successful, False otherwise.
        """
        return self._handle_task(
            self._async_write_node_value(path, value, remote_resource_spec)
        )

    @abstractmethod
    async def _async_write_node_value(
        self,
        path: str,
        value: Any,
        remote_resource_spec: AbstractRemoteResourceSpec | None,
    ) -> bool:
        """Asynchronous code which writes a variable node.

        Args:
            path (str):
                Node's path.
            value (Any):
                New value to write.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            bool:
                True if the operation was successful, False otherwise.
        """

    @override
    def call_node_as_method(
        self,
        path: str,
        kwargs: dict[str, Any],
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> Any:
        """Invokes the method with path <path> using <kwargs>.

        Args:
            path (str):
                Node/method path.
            kwargs (dict[str, Any]):
                Method arguments expressed as key/name - value pairs
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                Method's returned value.
        """
        return self._handle_task(
            self._async_call_node_as_method(path, kwargs, remote_resource_spec)
        )

    @abstractmethod
    async def _async_call_node_as_method(
        self,
        path: str,
        kwargs: dict[str, Any],
        remote_resource_spec: AbstractRemoteResourceSpec | None,
    ) -> Any:
        """Asynchronously invokes the method with path <path> using <kwargs>.

        Args:
            path (str):
                Node/method path.
            kwargs (dict[str, Any]):
                Method arguments expressed as key/name - value pairs.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                Method's returned value.
        """

    @override
    def subscribe_to_node_changes(
        self,
        path: str,
        callback: Callable[[Any, SubscriptionArguments], None],
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> int:
        """Subscribes to remote node changes.

        Args:
            path (str):
                Node path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.
            callback (Callable[[Any, SubscriptionArguments], None]):
                Subscription's callback. The first parameter is the new value,
                while the second parameter is additional data that is protocol
                dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """
        return self._handle_task(
            self._async_subscribe_to_node_changes(
                path,
                remote_resource_spec,
                callback,  # Correct order
            )
        )

    @abstractmethod
    async def _async_subscribe_to_node_changes(
        self,
        path: str,
        remote_resource_spec: AbstractRemoteResourceSpec | None,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        """Asynchronously subscribes to remote node changes.

        Args:
            path (str):
                Node path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.
            callback (Callable[[Any, SubscriptionArguments], None]):
                Subscription's callback. The first parameter is the new value,
                while the second parameter is additional data that is protocol
                dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """

    def _handle_task(
        self, task: Coroutine[None, None, TaskReturnType]
    ) -> TaskReturnType:
        """Run a task in the thread, wait for the result and return it.

        Args:
            task (Coroutine[None, None, TaskReturnType]):
                Coroutine which will be executed in the connector's thread.

        Returns:
            TaskReturnType:
                Coroutine result.
        """
        _logger.debug(f"Running task {task} using '{self.name}' connector")
        res = run_coroutine_in_thread(self._event_loop, task)
        output = res.result()
        _logger.debug(
            f"Ran task {task} using '{self.name}' connector. "
            f"Its result is {output!r}"
        )
        return output
