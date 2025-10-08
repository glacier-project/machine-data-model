import os
from dataclasses import dataclass
import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Any, TypeVar, Callable, Type
import logging

TaskReturnType = TypeVar("TaskReturnType")
YamlEntryType = int | str | float

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
        ip_env_var: str | None = None,
        port: int | None = None,
        port_env_var: str | None = None,
        username: str | None = None,
        username_env_var: str | None = None,
        password: str | None = None,
        password_env_var: str | None = None,
    ) -> None:
        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name: str | None = name

        ip_value = self._get_yaml_entry_or_env_var_value(
            "ip", str, ip, ip_env_var, env_var_overrides_yaml=True
        )
        assert isinstance(ip_value, (str, type(None))), "ip must be a str or None"
        self._ip: str | None = ip_value

        port_value = self._get_yaml_entry_or_env_var_value(
            "port", int, port, port_env_var, env_var_overrides_yaml=True
        )
        assert isinstance(port_value, (int, type(None))), "port must be a int or None"
        self._port = port_value

        username_value = self._get_yaml_entry_or_env_var_value(
            "username", str, username, username_env_var
        )
        assert isinstance(
            username_value, (str, type(None))
        ), "username must be a str or None"
        self._username = username_value

        password_value = self._get_yaml_entry_or_env_var_value(
            "password", str, password, password_env_var
        )
        assert isinstance(
            password_value, (str, type(None))
        ), "password must be a str or None"
        self._password = password_value

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

    def _get_yaml_entry_or_env_var_value(
        self,
        yaml_entry_name: str,
        yaml_entry_type: Type[YamlEntryType],
        yaml_entry: YamlEntryType | None,
        env_var: str | None,
        env_var_overrides_yaml: bool = False,
    ) -> YamlEntryType | None:
        """
        Returns the content of the env_var environment variable when set,
        otherwise it returns yaml_entry.

        When env_var_overrides_yaml is False, the function can throw an error to indicate
        that the user must either specify env_var or yaml_entry, but not both.

        If env_var_overrides_yaml is True, the env_var environment variable content always overrides the yaml_entry,
        without throwing exceptions.
        > This can be useful when the yaml_entry has a default value.

        > The function type casts the value to the yaml_entry_type type automatically.
        """

        if (
            not env_var_overrides_yaml
            and yaml_entry is not None
            and env_var is not None
        ):
            raise ValueError(
                f"Connector '{self.name}': only set one of the following attributes: '{yaml_entry_name}' or '{env_var}'"
            )

        if env_var is not None and os.getenv(env_var) is None:
            raise ValueError(
                f"Connector '{self.name}': environment variable '{env_var}' is not set"
            )

        value = os.environ.get(env_var) if env_var is not None else yaml_entry

        if value is not None:
            value = yaml_entry_type(value)
        return value

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
