import queue
from threading import Thread, Event
import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Coroutine, Any

from machine_data_model.nodes.connectors.connector_thread import ConnectorThread
from machine_data_model.nodes.data_model_node import DataModelNode


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
    ):
        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name: str | None = name
        self._ip: str | None = ip
        self._port: int | None = port
        self._tasks_queue: queue.Queue = queue.Queue()
        self._results_queue: queue.Queue = queue.Queue()
        self._thread_stop_event = Event()
        self._thread: Thread = ConnectorThread(
            self._thread_stop_event, self._tasks_queue, self._results_queue
        )
        self._thread.start()

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
    async def connect(self) -> None:
        """
        Connect to the server.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the server.
        """
        pass

    @abstractmethod
    def get_node(self, path: str) -> DataModelNode | None:
        """
        Try to retrieve the node from the server.
        """
        pass

    def stop_thread(self) -> None:
        """
        Stop the thread.
        """
        self._thread_stop_event.set()
        self._thread.join()

    def _handle_task(self, task: Coroutine) -> Any:
        """
        Run a task in the thread, wait for the result and return it.
        """
        self._tasks_queue.put(task)
        self._tasks_queue.join()
        output = self._results_queue.get()
        self._results_queue.task_done()
        return output

    def __iter__(self) -> Iterator["AbstractConnector"]:
        for _ in []:
            yield _
