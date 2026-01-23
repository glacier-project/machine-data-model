"""Abstract Connector classes.

This module defines the AbstractConnector abstract class,
which needs to be extended by all the other (synchronous) connectors.
> The connectors that have an asynchronous implementation need to extend the
AbstractAsyncConnector class instead.

The SubscriptionArguments class is used to specify
the arguments that are given to a subscription's callback.
> This class also needs to be extended and is connector/protocol specific.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
import os
from typing import Any, TypeVar
import uuid

from .abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)

TaskReturnType = TypeVar("TaskReturnType")
YamlEntryType = int | str | float

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionArguments:
    """Represents the arguments passed to a subscription's callback."""


class AbstractConnector(ABC):
    """Represents a generic connector/client."""

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
        """AbstractConnector constructor.

        Args:
            id (str | None):
                Connector's object id.
            name (str | None):
                Connector's name/identifier.
            ip (str | None):
                Server's IP address.
            ip_env_var (str | None):
                Environment variable which contains the server's IP address.
            port (int | None):
                Server's port.
            port_env_var (str | None):
                Environment variable which contains the server's port.
            username (str | None):
                Username used to authenticate to the server.
            username_env_var (str | None):
                Environment variable which contains the username used to
                authenticate to the server.
            password (str | None):
                Password used to authenticate to the server.
            password_env_var (str | None):
                Environment variable which contains the password used to
                authenticate to the server.
        """
        self.id: str = str(uuid.uuid4()) if id is None else id
        self.name: str | None = name

        self.ip_env_var: str | None = ip_env_var

        ip_value = self._get_yaml_entry_or_env_var_value(
            "ip", str, ip, ip_env_var, env_var_overrides_yaml=True
        )
        assert isinstance(ip_value, str | None), "ip must be a str or None"
        self.ip: str | None = ip_value

        self.port_env_var: str | None = port_env_var
        port_value = self._get_yaml_entry_or_env_var_value(
            "port", int, port, port_env_var, env_var_overrides_yaml=True
        )
        assert isinstance(port_value, int | None), "port must be a int or None"
        self.port = port_value

        username_value = self._get_yaml_entry_or_env_var_value(
            "username", str, username, username_env_var
        )
        assert isinstance(
            username_value, str | None
        ), "username must be a str or None"
        self.username = username_value

        password_value = self._get_yaml_entry_or_env_var_value(
            "password", str, password, password_env_var
        )
        assert isinstance(
            password_value, str | None
        ), "password must be a str or None"
        self.password = password_value

    def _get_yaml_entry_or_env_var_value(
        self,
        yaml_entry_name: str,
        yaml_entry_type: type[YamlEntryType],
        yaml_entry: YamlEntryType | None,
        env_var: str | None,
        env_var_overrides_yaml: bool = False,
    ) -> YamlEntryType | None:
        """Returns the value of a yaml entry or an environment variable.

        Returns the content of the env_var environment variable when set,
        otherwise it returns yaml_entry.

        When env_var_overrides_yaml is False, the function can throw an error
        to indicate that the user must either specify env_var or yaml_entry,
        but not both.

        If env_var_overrides_yaml is True, the env_var environment variable
        content always overrides the yaml_entry, without throwing exceptions.
        > This can be useful when the yaml_entry has a default value.
        > The function type casts the value to the yaml_entry_type type
        > automatically.

        Args:
            yaml_entry_name (str):
                The name of the yaml_entry.
            yaml_entry_type (Type[YamlEntryType]):
                The data type of the yaml_entry.
            yaml_entry (YamlEntryType | None):
                The content of the yaml_entry.
            env_var (str | None):
                The name of the environment variable.
            env_var_overrides_yaml (bool):
                When false, raise an exception if both the yaml_entry and
                env_var are set. When true, this method returns the env_var
                environment variable content (unless env_var is None).

        Returns:
            YamlEntryType | None:
                Either the content of the env_var environment variable or the
                yaml_entry.
        """
        if (
            not env_var_overrides_yaml
            and yaml_entry is not None
            and env_var is not None
        ):
            raise ValueError(
                f"Connector '{self.name}': only set one of the following "
                f"attributes: '{yaml_entry_name}' or '{env_var}'"
            )

        if env_var is not None and os.getenv(env_var) is None:
            raise ValueError(
                f"Connector '{self.name}': environment variable '{env_var}' is "
                f"not set"
            )

        value = os.environ.get(env_var) if env_var is not None else yaml_entry

        if value is not None:
            value = yaml_entry_type(value)
        return value

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the server.

        Returns:
            bool:
                True if the client is connected to the server.
        """

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the server.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """

    @abstractmethod
    def _get_remote_node(
        self,
        path: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> Any:
        """Try to retrieve the node from the server.

        The node's type depends on the library used to interact with the server.

        Args:
            path (str | None):
                Node's path.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                The node retrieved from the server.
        """

    @abstractmethod
    def read_node_value(
        self,
        path: str,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> Any:
        """Retrieve and return a node's value.

        Args:
            path:
                Node's path.
            remote_resource_spec:
                Protocol-specific properties for remote nodes.

        Returns:
            Any:
                The node's value.
        """

    @abstractmethod
    def write_node_value(
        self,
        path: str,
        value: Any,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> bool:
        """Write a variable node.

        Args:
            path (str):
                Node's path.
            value (Any):
                New value to write.
            remote_resource_spec:
                Protocol-specific properties for remote nodes.

        Returns:
            bool:
                True if the value was written successfully.
        """

    @abstractmethod
    def call_node_as_method(
        self,
        path: str,
        kwargs: dict[str, Any],
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> dict[str, Any]:
        """Calls the method at path <path> with <kwargs> as its arguments.

        Args:
            path (str):
                Node/method path.
            kwargs (dict[str, Any]):
                Method arguments expressed as key/name - value pairs.
            remote_resource_spec:
                Protocol-specific properties for remote nodes.

        Returns:
            dict[str, Any]:
                Dict of results in the form of name - value pairs.
        """

    @abstractmethod
    def subscribe_to_node_changes(
        self,
        path: str,
        callback: Callable[[Any, SubscriptionArguments], None],
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ) -> int:
        """Subscribes to remote node changes.

        Calls the callback function every time the remote value changes.

        The callback must accept two parameters:
        - the new remote value
        - other data. It can be used to pass different data depending on the
        Connector's protocol/implementation

        Args:
            path (str):
                Node's path.
            callback (Callable[[Any, SubscriptionArguments], None]):
                Subscription's callback. The first parameter is the new value,
                while the second parameter is additional data that is protocol
                dependent.
            remote_resource_spec:
                Protocol-specific properties for remote nodes.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """
