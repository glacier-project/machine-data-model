from dataclasses import dataclass
from threading import Thread
import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Any, TypeVar, Callable

from machine_data_model.nodes.data_model_node import DataModelNode
import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Coroutine
from concurrent.futures import Future

TaskReturnType = TypeVar("TaskReturnType")


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

    event_loop = asyncio.new_event_loop()
    thread = Thread(target=start_background_loop, args=(event_loop,), daemon=True)
    thread.start()
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


@dataclass(frozen=True)
class SubscriptionArguments:
    """
    Superclass which is common for all data that is returned
    to subscription callbacks.
    """

    pass


class AbstractConnector(ABC):
    """
    Represents a generic connector/client.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        ip: str | None = None,
        port: int | None = None,
        event_loop: AbstractEventLoop | None = None,
    ) -> None:
        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name: str | None = name
        self._ip: str | None = ip
        self._port: int | None = port

        self._event_loop = (
            create_event_loop_thread() if event_loop is None else event_loop
        )

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def ip(self) -> str | None:
        return self._ip

    @property
    def port(self) -> int | None:
        return self._port

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the server.

        :return: True if the client is connected to the server
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the server.

        :return: True if the client is disconnected from the server
        """
        pass

    @abstractmethod
    def get_data_model_node(
        self, path: str, stub_node: DataModelNode | None = None
    ) -> DataModelNode | None:
        """
        Try to retrieve the node from the server
        and to convert it to a DataModelNode before returning it.

        :param path: node's path
        :param stub_node: local node, its information is used to create the remote node
        """
        pass

    @abstractmethod
    def _get_remote_node(self, path: str) -> Any:
        """
        Try to retrieve the node from the server.
        The node's type depends on the library used to interact with the server.

        :param path: node's path
        """
        pass

    @abstractmethod
    def read_node_value(self, path: str) -> Any:
        """
        Retrieve and return a node's value.
        :param path: node's path
        """
        pass

    @abstractmethod
    def write_node_value(self, path: str, value: Any) -> bool:
        """
        Write a variable node.

        :param path: node's path
        :param value: new value to write
        """
        pass

    @abstractmethod
    def call_node_as_method(self, path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Calls the method at path <path> with <kwargs> as its arguments.

        :param path: node/method path
        :param kwargs: method arguments expressed as key/name - value pairs
        :return: dict of results in the form of name - value pairs
        """
        pass

    @abstractmethod
    def subscribe_to_node_changes(
        self, path: str, callback: Callable[[Any, SubscriptionArguments], None]
    ) -> int:
        """
        Subscribes to remote node changes.
        Calls the callback function every time the remote value changes.

        The callback must accept two parameters:
        - the new remote value
        - other data. It can be used to pass different data depending on the Connector's protocol/implementation

        :param path: node path
        :param callback: callback
        :return: handler code which can be used to unsubscribe from new events
        """
        pass

    def stop_thread(self) -> None:
        """
        Stops the thread. Calls disconnect() automatically to disconnect from the server.
        """
        self.disconnect()
        self._event_loop.stop()

    def _handle_task(
        self, task: Coroutine[None, None, TaskReturnType]
    ) -> TaskReturnType:
        """
        Run a task in the thread, wait for the result and return it.
        """
        res = run_coroutine_in_thread(self._event_loop, task)
        output = res.result()
        return output

    def __iter__(self) -> Iterator["AbstractConnector"]:
        for _ in []:
            yield _
