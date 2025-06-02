import queue
import warnings
from threading import Thread, Event
import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Coroutine

from machine_data_model.nodes.connectors.connector_thread import (
    ConnectorThread,
    TaskReturnType,
)
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

        # -- thread management
        self._tasks_queue: queue.Queue = queue.Queue()
        self._results_queue: queue.Queue = queue.Queue()
        self._thread_stop_event = Event()
        self._thread: Thread = ConnectorThread(
            self._thread_stop_event, self._tasks_queue, self._results_queue
        )
        # True if the ConnectorThread is already running a task
        self._is_task_running = False

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
    def connect(self) -> None:
        """
        Connect to the server.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
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

    def _handle_task(
        self, task: Coroutine[None, None, TaskReturnType]
    ) -> TaskReturnType:
        """
        Run a task in the thread, wait for the result and return it.
        """
        if self._is_task_running:
            warnings.warn(
                "Trying to run a task inside the task that is currently running in this ConnectorThread: "
                "this will likely cause a deadlock. Make sure that there are no (direct or indirect) calls "
                "to _handle_task() inside tasks run by _handle_task()."
            )
        self._is_task_running = True
        self._tasks_queue.put(task)
        self._tasks_queue.join()
        output: TaskReturnType = self._results_queue.get()
        self._results_queue.task_done()
        self._is_task_running = False
        return output

    def __iter__(self) -> Iterator["AbstractConnector"]:
        for _ in []:
            yield _
