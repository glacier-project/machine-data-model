from threading import Thread
from abc import abstractmethod
from typing import Iterator, Any, TypeVar, Callable
import logging

import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Coroutine
from concurrent.futures import Future
from typing_extensions import override

from .abstract_connector import AbstractConnector, SubscriptionArguments

TaskReturnType = TypeVar("TaskReturnType")

_logger = logging.getLogger(__name__)


def create_event_loop_thread() -> AbstractEventLoop:
    """
    Creates a thread with an asyncio loop.
    The loop can then be used to execute the async tasks inside the thread.

    Credits:
    https://gist.github.com/dmfigol/3e7d5b84a16d076df02baa9f53271058?permalink_comment_id=5553292#gistcomment-5553292
    """

    def start_background_loop(loop: AbstractEventLoop) -> None:
        """
        Runs the asyncio loop forever.
        """
        asyncio.set_event_loop(loop)
        loop.run_forever()

    _logger.debug("Creating thread and its event loop")
    event_loop = asyncio.new_event_loop()
    thread = Thread(target=start_background_loop, args=(event_loop,), daemon=True)
    thread.start()
    _logger.debug("Created thread and its event loop")
    return event_loop


def run_coroutine_in_thread(
    loop: AbstractEventLoop, coro: Coroutine[None, None, TaskReturnType]
) -> Future[TaskReturnType]:
    """
    Runs a coroutine in a thread.
    Use create_event_loop_thread() to get the loop.

    Credits:
    https://gist.github.com/dmfigol/3e7d5b84a16d076df02baa9f53271058?permalink_comment_id=5553292#gistcomment-5553292
    """
    return asyncio.run_coroutine_threadsafe(coro, loop)


class AbstractAsyncConnector(AbstractConnector):
    """
    Represents a generic connector/client,
    where the client's library has an asynchronous implementation.
    """

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
        """
        Connect to the server.
        Wraps its asynchronous implementation.

        Returns:
            bool:
                True if the client is connected to the server.
        """
        return self._handle_task(self._async_connect())

    @abstractmethod
    async def _async_connect(self) -> bool:
        """
        Asynchronous code which uses the client to connect to the server.

        Returns:
            bool:
                True if the client is connected to the server.
        """

    @override
    def disconnect(self) -> bool:
        """
        Disconnect from the server.
        Wraps its asynchronous implementation.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """
        res = self._handle_task(self._async_disconnect())
        self._event_loop.stop()
        return res

    @abstractmethod
    async def _async_disconnect(self) -> bool:
        """
        Asynchronous code which uses the client to disconnect from the server.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """

    @override
    def _get_remote_node(self, path: str) -> Any:
        """
        Try to retrieve the node from the server.
        The node's type depends on the library used to interact with the server.
        Wraps its asynchronous implementation.

        Args:
            path (str):
                Node's path.

        Returns:
            Any:
                Node with the given path.
        """
        return self._handle_task(self._async_get_remote_node(path))

    @abstractmethod
    async def _async_get_remote_node(self, path: str) -> Any:
        """
        Asynchronous code which uses the client to retrieve the node from the server.

        Args:
            path (str):
                Node's path.

        Returns:
            Any:
                Node with the given path.
        """

    @override
    def read_node_value(self, path: str) -> Any:
        """
        Retrieve and return a node's value.
        Wraps its asynchronous implementation.

        Args:
            path (str):
                Node's path.

        Returns:
            Any:
                Node's value.
        """
        return self._handle_task(self._async_read_node_value(path))

    @abstractmethod
    async def _async_read_node_value(self, path: str) -> Any:
        """
        Asynchronous code which reads a node's value.

        Args:
            path (str):
                Node's path.

        Returns:
            Any:
                Node's value.
        """

    @override
    def write_node_value(self, path: str, value: Any) -> bool:
        """
        Write a variable node.
        Wraps its asynchronous implementation.

        Args:
            path (str):
                Node's path.
            value (Any):
                New value to write.

        Returns:
            bool:
                True if the operation was successful, False otherwise.
        """
        return self._handle_task(self._async_write_node_value(path, value))

    @abstractmethod
    async def _async_write_node_value(self, path: str, value: Any) -> bool:
        """
        Asynchronous code which writes a variable node.

        Args:
            path (str):
                Node's path.
            value (Any):
                New value to write.

        Returns:
            bool:
                True if the operation was successful, False otherwise.
        """

    @override
    def call_node_as_method(self, path: str, kwargs: dict[str, Any]) -> Any:
        """
        Calls the method at path <path> with <kwargs> as its arguments.
        Wraps its asynchronous implementation.

        Args:
            path (str):
                Node/method path.
            kwargs (dict[str, Any]):
                Method arguments expressed as key/name - value pairs

        Returns:
            Any:
                Method's returned value.
        """
        return self._handle_task(self._async_call_node_as_method(path, kwargs))

    @abstractmethod
    async def _async_call_node_as_method(
        self, path: str, kwargs: dict[str, Any]
    ) -> Any:
        """
        Asynchronous code which calls the method at path <path> with <kwargs> as its arguments.

        Args:
            path (str):
                Node/method path.
            kwargs (dict[str, Any]):
                Method arguments expressed as key/name - value pairs.

        Returns:
            dict[str, Any]:
                Method's returned value.
        """

    @override
    def subscribe_to_node_changes(
        self, path: str, callback: Callable[[Any, SubscriptionArguments], None]
    ) -> int:
        """
        Subscribes to remote node changes.
        Calls the callback function every time the remote value changes.
        Wraps its asynchronous implementation.

        The callback must accept two parameters:
        - the new remote value
        - other data. It can be used to pass different data depending on the Connector's protocol/implementation

        Args:
            path (str):
                Node path.
            callback (Callable[[Any, SubscriptionArguments], None]):
                Subscription's callback. The first parameter is the new value, while the
                second parameter is additional data that is protocol dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """
        return self._handle_task(self._async_subscribe_to_node_changes(path, callback))

    @abstractmethod
    async def _async_subscribe_to_node_changes(
        self, path: str, callback: Callable[[Any, SubscriptionArguments], None]
    ) -> int:
        """
        Asynchronous code which subscribes to remote node changes.
        Calls the callback function every time the remote value changes.

        The callback must accept two parameters:
        - the new remote value
        - other data. It can be used to pass different data depending on the Connector's protocol/implementation

        Args:
            path (str):
                Node path.
            callback (Callable[[Any, SubscriptionArguments], None]):
                Subscription's callback. The first parameter is the new value, while the
                second parameter is additional data that is protocol dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """

    def _handle_task(
        self, task: Coroutine[None, None, TaskReturnType]
    ) -> TaskReturnType:
        """
        Run a task in the thread, wait for the result and return it.

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
            f"Ran task {task} using '{self.name}' connector. Its result is {output!r}"
        )
        return output

    def __iter__(self) -> Iterator["AbstractAsyncConnector"]:
        for _ in []:
            yield _
