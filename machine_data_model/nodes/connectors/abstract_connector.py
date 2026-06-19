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
import os
from typing import Any, TypeVar
import uuid

from .remote_resource import RemoteResource

ConnectorConfigValue = TypeVar("ConnectorConfigValue", int, str, float)


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
        self.ip = ip_value

        self.port_env_var: str | None = port_env_var
        port_value = self._get_yaml_entry_or_env_var_value(
            "port", int, port, port_env_var, env_var_overrides_yaml=True
        )
        self.port = port_value

        self.username_env_var: str | None = username_env_var
        username_value = self._get_yaml_entry_or_env_var_value(
            "username", str, username, username_env_var
        )
        self.username = username_value

        self.password_env_var: str | None = password_env_var
        password_value = self._get_yaml_entry_or_env_var_value(
            "password", str, password, password_env_var
        )
        self.password = password_value

    def _get_yaml_entry_or_env_var_value(
        self,
        yaml_entry_name: str,
        yaml_entry_type: type[ConnectorConfigValue],
        yaml_entry: ConnectorConfigValue | None,
        env_var: str | None,
        env_var_overrides_yaml: bool = False,
    ) -> ConnectorConfigValue | None:
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
    def _get_remote_resource(self, resource: RemoteResource) -> Any:
        """Resolve the protocol-specific object behind a remote resource.

        The returned type depends on the connector implementation. It can be a
        remote node, a topic, an address, or any other protocol handle.

        Args:
            resource:
                Resolved remote resource reference.

        Returns:
            Any:
                The protocol-specific resource handle.
        """

    @abstractmethod
    def read_node_value(self, resource: RemoteResource) -> Any:
        """Retrieve and return a node's value.

        Args:
            resource:
                Resolved remote resource reference.

        Returns:
            Any:
                The node's value.
        """

    @abstractmethod
    def write_node_value(
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        """Write a variable node.

        Args:
            resource:
                Resolved remote resource reference.
            value:
                New value to write.

        Returns:
            bool:
                True if the value was written successfully.
        """

    @abstractmethod
    def call_node_as_method(
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        """Call a remote method with ``kwargs`` as its arguments.

        Args:
            resource:
                Resolved remote resource reference.
            kwargs:
                Method arguments expressed as key/name - value pairs.

        Returns:
            Any:
                Method's returned value.
        """

    @abstractmethod
    def subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        """Subscribes to remote node changes.

        Calls the callback function every time the remote value changes.

        The callback must accept two parameters:
        - the new remote value
        - other data. It can be used to pass different data depending on the
        Connector's protocol/implementation

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

    @abstractmethod
    def unsubscribe_from_node_changes(self, handle: int) -> bool:
        """Unsubscribes from remote node changes.

        Consumes the handle returned by ``subscribe_to_node_changes`` and stops
        delivering updates to that subscription's callback.

        Args:
            handle:
                Handler code returned by ``subscribe_to_node_changes``.

        Returns:
            bool:
                True if the subscription was found and removed.
        """
