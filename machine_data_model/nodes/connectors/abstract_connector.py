import os
from dataclasses import dataclass
import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Any, TypeVar, Callable
import logging

TaskReturnType = TypeVar("TaskReturnType")

_logger = logging.getLogger(__name__)


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
        username: str | None = None,
        password: str | None = None,
        password_env_var: str | None = None,
    ) -> None:
        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name: str | None = name
        self._ip: str | None = ip
        self._port: int | None = port
        self._username: str | None = username

        if password is not None and password_env_var is not None:
            raise ValueError(
                f"Connector '{self.name}': only set one of the following attributes: 'password' or 'password_env_var'"
            )

        if password_env_var is not None and os.getenv(password_env_var) is None:
            raise ValueError(
                f"Connector '{self.name}': password environment variable '{password_env_var}' is not set"
            )

        self._password: str | None = (
            os.environ.get(password_env_var)
            if password_env_var is not None
            else password
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

    def __iter__(self) -> Iterator["AbstractConnector"]:
        for _ in []:
            yield _
