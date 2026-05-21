"""OPC UA connector classes.

This module defines the OpcuaConnector class,
which is an asynchronous connector for the OPC UA protocol.
> It is asynchronous because asyncua, the library used to interact with OPC UA,
> is implemented with the async/await paradigm.

The OpcuaSubscriptionArguments class defines the parameters
that are given to the OpcuaConnector subscription's callback.

The OpcuaRemoteResourceSpec class defines all the properties
of DataModelNodes that are specific to OPC UA.
> The user sets their value in the data model yaml file
"""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path
import socket
from typing import Any, cast

import asyncua
from asyncua import Client as AsyncuaClient
from asyncua.common.subscription import (
    DataChangeNotif,
    DataChangeNotificationHandler,
)
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto.security_policies import (
    SecurityPolicy,
    SecurityPolicyBasic256Sha256,
)
from asyncua.crypto.truststore import TrustStore
from asyncua.crypto.validator import (
    CertificateValidator,
    CertificateValidatorOptions,
)
from asyncua.ua import UaError, VariantType
from cryptography.x509.oid import ExtendedKeyUsageOID
from typing_extensions import override

from ..abstract_async_connector import AbstractAsyncConnector
from ..abstract_connector import SubscriptionArguments
from ..remote_resource import RemoteResource
from .opcua_remote_resource_spec import OpcuaRemoteResourceSpec

_logger = logging.getLogger(__name__)


def _require_asyncua_node(value: Any) -> asyncua.Node:
    """Return an asyncua node or fail with a clear connector error."""
    if not isinstance(value, asyncua.Node):
        raise TypeError(
            f"Expected an asyncua.Node, but got {type(value).__name__}"
        )
    return value


@dataclass(frozen=True)
class OpcuaSubscriptionArguments(SubscriptionArguments):
    """Data returned to the OPC UA subscription callback."""

    node: asyncua.Node
    value: Any
    notification: DataChangeNotif


def _security_policy_string_to_asyncua_policy(
    policy_string: str | None,
) -> type[SecurityPolicy] | None:
    """Converts a security policy string to an asyncua SecurityPolicy type.

    Args:
        policy_string (str | None):
            String which contains the desired security policy.

    Returns:
        type[SecurityPolicy] | None:
            Returns the asyncua security policy if it exists, None otherwise.
    """
    policy: type[SecurityPolicy] | None = None
    if policy_string == "SecurityPolicyBasic256Sha256":
        policy = SecurityPolicyBasic256Sha256

    return policy


async def get_input_arguments(node: asyncua.Node) -> asyncua.Node | None:
    """Returns the InputArguments node of a OPC UA method node.

    Given a OPCU UA method node, returns its input arguments.
    If the method doesn't have input arguments, it returns None.

    Args:
        node (asyncua.Node):
            The node to get the input arguments from.

    Returns:
        asyncua.Node | None:
            Returns the InputArguments node if it exists, None otherwise.
    """
    props = await node.get_properties()

    for prop in props:
        name = await prop.read_browse_name()
        name = name.Name
        if name == "InputArguments":
            return prop
    return None


class OpcuaConnector(AbstractAsyncConnector):
    """Represents an OPCUA client."""

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        ip: str | None = None,
        ip_env_var: str | None = None,
        port: int | None = None,
        port_env_var: str | None = None,
        security_policy: str | None = None,
        host_name: str | None = None,
        client_app_uri: str | None = None,
        private_key_file_path: str | None = None,
        certificate_file_path: str | None = None,
        trust_store_certificates_paths: list[str] | None = None,
        username: str | None = None,
        username_env_var: str | None = None,
        password: str | None = None,
        password_env_var: str | None = None,
    ) -> None:
        """Initializes an OPCUA client.

        Args:
            id (str | None):
                Node ID.
            name (str | None):
                Client name.
            ip (str | None):
                OPC UA server address.
            ip_env_var (str | None):
                Environment variable which contains the OPC UA server address.
            port (int | None):
                OPC UA server port.
            port_env_var (str | None):
                Environment variable which contains the OPC UA server port.
            security_policy (str | None):
                OPC UA security mode.
            host_name (str | None):
                Host name.
            client_app_uri (str | None):
                App URI.
            private_key_file_path (str | None):
                Path to the private key file.
            certificate_file_path (str | None):
                Path to the certificate file.
            trust_store_certificates_paths (list[str] | None):
                Paths which contains certificates for the trust store.
            username (str | None):
                OPC UA username. Keep it set to None if the username is not
                required.
            username_env_var (str | None):
                Environment variable which contains the OPC UA username.
            password (str | None):
                OPC UA password. Keep it set to None if the password is not
                required.
            password_env_var (str | None):
                Environment variable which contains the OPC UA password.
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
        self.security_policy: str | None = security_policy
        self.client: AsyncuaClient | None = None
        self.host_name: str = (
            host_name if host_name is not None else socket.gethostname()
        )
        self.client_app_uri: str = (
            client_app_uri
            if client_app_uri is not None
            else self.get_default_client_app_uri()
        )

        if private_key_file_path is None:
            _logger.warning(
                f"Connector {self.name} doesn't have 'private_key_file_path' "
                f"attribute specified: a private key will be generated and "
                f"used automatically"
            )

        if certificate_file_path is None:
            _logger.warning(
                f"Connector {self.name} doesn't have 'certificate_file_path' "
                f"attribute specified: a self-signed certificate will be "
                f"generated and used automatically"
            )

        self.private_key_file_path: Path = (
            Path(private_key_file_path)
            if private_key_file_path is not None
            else self.get_default_private_key_file_path()
        )
        self.certificate_file_path: Path = (
            Path(certificate_file_path)
            if certificate_file_path is not None
            else self.get_default_certificate_file_path()
        )

        # pyrefly: ignore[implicit-any-type-argument]
        if not isinstance(trust_store_certificates_paths, list | None):
            raise TypeError(
                f"Connector '{name}': trust_store_certificates_paths, when "
                f"defined, must be a list of strings"
            )

        self.trust_store_certificates_paths: list[Path] = []
        if trust_store_certificates_paths is not None:
            if len(trust_store_certificates_paths) == 0:
                raise ValueError(
                    f"Connector '{name}': trust_store_certificates_paths cannot"
                    f" be defined but also empty. Please, remove the "
                    f"'trust_store_certificates_paths' attribute or add valid "
                    f"paths to the list"
                )
            for path_string in trust_store_certificates_paths:
                if not isinstance(path_string, str):
                    raise TypeError(
                        f"Connector '{name}': The '{path_string}' path inside "
                        f"trust_store_certificates_paths is not a string"
                    )
                trust_store_cert_path = Path(path_string)
                if not trust_store_cert_path.is_dir():
                    raise ValueError(
                        f"Connector '{name}': The '{path_string}' path inside "
                        f"trust_store_certificates_paths is not a directory"
                    )
                self.trust_store_certificates_paths.append(
                    trust_store_cert_path
                )

    def get_default_client_app_uri(self) -> str:
        """Returns a default client application URI.

        Returns:
            str:
                Default client application URI.
        """
        return f"urn:{self.host_name}:foobar:myselfsignedclient"

    def get_default_private_key_file_path(self) -> Path:
        """Returns a default path to the private key file.

        Returns:
            Path:
                Default path to the private key file.
        """
        return Path("private.selfsigned.pem")

    def get_default_certificate_file_path(self) -> Path:
        """Returns a default path to the certificate file.

        Returns:
            Path:
                Default path to the certificate file.
        """
        return Path("cert.selfsigned.der")

    @override
    async def _async_connect(self) -> bool:
        """Asynchronously connects to the OPC UA server.

        Returns:
            bool:
                True if the client is connected to the server.
        """
        url = f"opc.tcp://{self.ip}:{self.port}"
        _logger.debug(
            f"Connecting '{self.name}' connector to OPC UA server. Url is: "
            f"{url}"
        )
        _logger.debug(
            f"Setting up the certificates for the '{self.name}' connector."
        )

        try:
            await setup_self_signed_certificate(
                self.private_key_file_path,
                self.certificate_file_path,
                self.client_app_uri,
                self.host_name,
                [ExtendedKeyUsageOID.CLIENT_AUTH],
                {
                    "countryName": "CN",
                    "stateOrProvinceName": "AState",
                    "localityName": "Foo",
                    "organizationName": "Bar Ltd",
                },
            )
        except FileNotFoundError as e:
            _logger.error(e)
            return False

        client = AsyncuaClient(url=url)
        client.application_uri = self.client_app_uri

        if self.username:
            client.set_user(self.username)

        if self.password:
            client.set_password(self.password)

        security_policy = _security_policy_string_to_asyncua_policy(
            self.security_policy
        )

        if security_policy is not None:
            _logger.debug(
                f"Setting up the security policy for the '{self.name}' "
                f"connector. Policy is: {security_policy}"
            )
            try:
                await client.set_security(
                    security_policy,
                    certificate=self.certificate_file_path,
                    private_key=self.private_key_file_path,
                    server_certificate=None,  # "certificate-example.der",
                )
            except (ConnectionRefusedError, TimeoutError) as e:
                _logger.error(e)
                return False

        _logger.debug(
            f"Setting up the certificate validator for the '{self.name}' "
            f"connector"
        )

        if len(self.trust_store_certificates_paths) > 0:
            trust_store = TrustStore(self.trust_store_certificates_paths, [])
            await trust_store.load()
            validator = CertificateValidator(
                CertificateValidatorOptions.TRUSTED_VALIDATION
                | CertificateValidatorOptions.PEER_SERVER,
                trust_store,
            )
        else:
            validator = CertificateValidator(
                CertificateValidatorOptions.EXT_VALIDATION
                | CertificateValidatorOptions.PEER_SERVER
            )
        client.certificate_validator = validator

        self.client = client
        try:
            await self.client.connect()
        except Exception as e:
            _logger.debug(
                f"Couldn't connect the '{self.name}' connector to the OPC UA "
                f"server"
            )
            _logger.error(e)
            return False
        _logger.debug(
            f"Connected the '{self.name}' connector to the OPC UA server"
        )
        return True

    @override
    async def _async_disconnect(self) -> bool:
        """Asynchronously disconnects from the OPC UA server.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """
        _logger.debug(
            f"Disconnecting '{self.name}' connector from OPC UA server"
        )
        if self.client is None:
            _logger.debug(
                f"The '{self.name}' connector was already disconnected"
            )
            return True

        try:
            await self.client.disconnect()
        except Exception as e:
            _logger.error(f"Couldn't disconnect '{self.name}' connector")
            _logger.error(e)
            return False
        finally:
            self.client = None

        _logger.debug(f"Disconnected '{self.name}' connector")
        return True

    def _opcua_spec(
        self, resource: RemoteResource
    ) -> OpcuaRemoteResourceSpec | None:
        """Return the OPC UA spec or raise when another protocol is supplied."""
        if resource.spec is not None and not isinstance(
            resource.spec, OpcuaRemoteResourceSpec
        ):
            raise TypeError(
                "resource.spec must be an OpcuaRemoteResourceSpec or None"
            )
        return resource.spec

    @override
    async def _async_get_remote_resource(
        self, resource: RemoteResource
    ) -> asyncua.Node:
        """Resolve the OPC UA node for a remote resource."""
        remote_resource_spec = self._opcua_spec(resource)
        path = resource.path

        _logger.debug(f"Retrieving node '{path}' from OPC UA server")

        if self.client is None:
            raise RuntimeError(
                f"Couldn't retrieve remote node '{path}' using '{self.name}' "
                f"connector: the client is not connected"
            )

        node = None
        try:
            if remote_resource_spec is not None:
                if remote_resource_spec.has_remote_node():
                    _logger.debug(
                        f"Using already retrieved remote node for '{path}'"
                    )
                    return _require_asyncua_node(
                        remote_resource_spec.remote_node
                    )

                if remote_resource_spec.has_node_id():
                    _logger.debug(
                        f"Retrieving node by node id "
                        f"'{remote_resource_spec.node_id}'"
                    )
                    node = _require_asyncua_node(
                        self.client.get_node(
                            cast(Any, remote_resource_spec.node_id)
                        )
                    )
                    remote_resource_spec.remote_node = node
                    return node

                if remote_resource_spec.has_path():
                    path = (
                        remote_resource_spec.remote_path
                        if remote_resource_spec.remote_path is not None
                        else ""
                    )
            if not path:
                if remote_resource_spec is not None:
                    computed_path = remote_resource_spec.get_remote_path(
                        resource.node
                    )
                    if computed_path:
                        path = computed_path

                if not path:
                    raise ValueError(
                        f"Couldn't retrieve node '{path}': empty path"
                    )
            _logger.debug(
                f"Retrieving node '{resource.path}' by remote path '{path}'"
            )
            split_path = [p for p in path.split("/") if p]
            node = _require_asyncua_node(
                await self.client.get_root_node().get_child(split_path)
            )
            if remote_resource_spec is not None:
                remote_resource_spec.remote_node = node
                if not remote_resource_spec.has_node_id():
                    remote_resource_spec.node_id = node.nodeid.to_string()
            return node
        except UaError as exp:
            _logger.error(exp)

        raise ValueError(
            f"Couldn't retrieve node '{path}', {remote_resource_spec}",
            f" using the '{self.name}' " f"connector: the node doesn't exist",
        )

    async def _remote_node(self, resource: RemoteResource) -> asyncua.Node:
        """Resolve a resource and fail clearly when the node does not exist."""
        return await self._async_get_remote_resource(resource)

    @override
    async def _async_read_node_value(self, resource: RemoteResource) -> Any:
        """Asynchronously read the node's value from the server."""
        path = resource.path
        if self.client is None:
            raise RuntimeError(
                f"Couldn't read remote node '{path}' using '{self.name}' "
                f"connector: the client is not connected"
            )

        _logger.debug(f"Reading node '{path}'")
        node = await self._remote_node(resource)
        try:
            value = await node.get_value()
        except UaError as exp:
            raise ValueError(
                f"Couldn't read value of '{path}' using the '{self.name}' "
                f"connector: the node does not exist"
            ) from exp
        _logger.debug(f"Read node '{path}'. Its value is: {value!r}")
        return value

    @override
    async def _async_write_node_value(
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        """Asynchronously write the value to the OPC UA server."""
        path = resource.path
        if self.client is None:
            raise RuntimeError(
                f"Couldn't write remote node '{path}' using '{self.name}' "
                f"connector: the client is not connected"
            )

        _logger.debug(f"Writing node '{path}' with value: {value}")
        node = await self._remote_node(resource)

        success = True
        try:
            current_value = await node.read_data_value()
            # pyrefly: ignore[missing-attribute]
            current_value_type = current_value.Value.VariantType
            _logger.debug(
                f"Overriding node '{path}', which previously had value "
                f"{current_value!r} (type {current_value_type}), with value: "
                f"{value!r}"
            )
            await node.write_value(value, current_value_type)

            written_value = await node.get_value()
            if written_value != value:
                _logger.error(
                    f"Write verification failed for node '{path}': "
                    f"expected {value!r}, but got {written_value!r}"
                )
                success = False
        except UaError as exp:
            _logger.error(
                f"Failed to write node '{path}': {type(exp).__name__}: {exp}"
            )
            success = False

        _logger.debug(
            f"Written node '{path}' with value: {value}, success: {success}"
        )
        return success

    @override
    async def _async_call_node_as_method(
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        """Asynchronously call a method on the OPC UA server."""
        remote_resource_spec = self._opcua_spec(resource)
        path = resource.path
        _logger.debug(
            f"Calling remote method '{path}', with the following parameters: "
            f"{kwargs}"
        )
        if self.client is None:
            raise RuntimeError(
                f"Couldn't call remote method '{path}' using '{self.name}' "
                f"connector: the client is not connected"
            )

        node = await self._remote_node(resource)

        method_inputs = await get_input_arguments(node)
        inputs = []  # pyrefly: ignore[implicit-any-empty-container]
        if method_inputs is not None:
            inputs = await method_inputs.read_value()
            if not isinstance(inputs, list):
                raise TypeError(
                    f"Input arguments for method '{path}' must be a list"
                )

        params = []
        kwargs_list = list(kwargs.items())

        for i, ua_param in enumerate(inputs):
            dt = ua_param.DataType
            identifier = dt.Identifier
            variant_type = VariantType(identifier)

            if i < len(kwargs_list):
                param_name, value = kwargs_list[i]
                if value is not None:
                    params.append(asyncua.ua.Variant(value, variant_type))
                else:
                    _logger.warning(
                        f"Parameter '{param_name}' for method '{path}' is None",
                        f"expected type: {variant_type}. Skipping parameter.",
                    )
            else:
                _logger.warning(
                    f"Missing parameter at position {i} for method '{path}' - "
                    f"expected type: {variant_type}"
                )

        _logger.debug(
            f"Converted parameters of '{path}' into VariantTypes: {params}"
        )

        result = None
        parent = None
        try:
            _logger.debug(f"Calling '{path}' using the parent node. ")
            if (
                remote_resource_spec is not None
                and remote_resource_spec.has_parent_node_id()
            ):
                _logger.debug(
                    f"Using parent node id"
                    f"{remote_resource_spec.parent_node_id}"
                )
                parent = self.client.get_node(
                    cast(Any, remote_resource_spec.parent_node_id)
                )
            else:
                parent = await node.get_parent()
            parent = _require_asyncua_node(parent)
            result = await parent.call_method(node.nodeid, *params)
        except UaError as exp:
            _logger.error(
                f"Failed to call method '{path}': {type(exp).__name__}: {exp}"
            )
            raise ValueError(
                f"Couldn't call remote method '{path}',",
                f" '{remote_resource_spec}' using '{self.name}' ",
                f"connector: {exp}",
            ) from exp
        return result

    @override
    async def _async_subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, OpcuaSubscriptionArguments], None],
    ) -> int:
        """Asynchronously subscribe to changes of the remote node."""
        path = resource.path
        self._opcua_spec(resource)

        _logger.debug(f"Subscribing to remote node '{path}'")
        if self.client is None:
            raise RuntimeError(
                f"Couldn't subscribe to '{path}': Client is not running inside "
                f"the '{self.name}' connector"
            )

        handler = OpcUaDataChangeHandler(callback)
        subscription = await self.client.create_subscription(1, handler)
        node = await self._remote_node(resource)

        res = await subscription.subscribe_data_change(node)
        if not isinstance(res, int):
            raise TypeError("subscription handler must be an int")
        _logger.debug(
            f"Subscribed to remote node '{path}'. "
            f"Subscription handler code: {res}"
        )
        return res

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            dict[str, Any]:
                Dictionary with all properties.
        """
        return {
            "name": self.name,
            "id": self.id,
            "host_name": self.host_name,
            "client_app_uri": self.client_app_uri,
            "private_key_file_path": str(self.private_key_file_path),
            "certificate_file_path": str(self.certificate_file_path),
        }

    @override
    def __str__(self) -> str:
        return (
            "OpcuaConnector("
            f"name={self.name!r}, "
            f"id={self.id!r}, "
            f"ip={self.ip!r}, "
            f"port={self.port!r}, "
            f"security_policy={self.security_policy!r}, "
            f"host_name={self.host_name!r}, "
            f"client_app_uri={self.client_app_uri!r}, "
            f"private_key_file_path={self.private_key_file_path!r}, "
            f"certificate_file_path={self.certificate_file_path!r}"
            ")"
        )

    @override
    def __repr__(self) -> str:
        return self.__str__()


class OpcUaDataChangeHandler(DataChangeNotificationHandler):  # type: ignore[misc]
    """Handles OPC UA data changes by calling a callback function."""

    def __init__(
        self, callback: Callable[[Any, OpcuaSubscriptionArguments], None]
    ) -> None:
        """Stores the callback to be called when a remote value changes.

        Args:
            callback (Callable[[Any, OpcuaSubscriptionArguments], None]):
                Callback function to be called when a remote value changes.
        """
        self._callback = callback

    @override
    def datachange_notification(
        self, node: asyncua.Node, val: Any, data: DataChangeNotif
    ) -> None:
        """Called for every datachange notification from server.

        Args:
            node (asyncua.Node):
                Node whose data changed.
            val (Any):
                New data value.
            data (DataChangeNotif):
                Notification object about the data change.
        """
        _logger.debug(
            f"Received new datachange notification for node {node}. Its new "
            f"value is: {val!r}"
        )
        other = OpcuaSubscriptionArguments(
            node=node, value=val, notification=data
        )
        self._callback(val, other)
