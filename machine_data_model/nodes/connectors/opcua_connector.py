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
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from machine_data_model.nodes.data_model_node import DataModelNode

from .abstract_async_connector import AbstractAsyncConnector
from .abstract_connector import SubscriptionArguments
from .remote_resource_spec import RemoteResourceSpec

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpcuaSubscriptionArguments(SubscriptionArguments):
    """Data returned to the OPC-UA subscription callback."""

    node: asyncua.Node
    value: Any
    notification: DataChangeNotif


def _security_policy_string_to_asyncua_policy(
    policy_string: str | None,
) -> type[SecurityPolicy] | None:
    """Converts a string containing the desired security policy into an asyncua
    SecurityPolicy type.

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
    """Given a method node, returns its input arguments.
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
                OPC-UA server address.
            ip_env_var (str | None):
                Environment variable which contains the OPC-UA server address.
            port (int | None):
                OPC-UA server port.
            port_env_var (str | None):
                Environment variable which contains the OPC-UA server port.
            security_policy (str | None):
                OPC-UA security mode.
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
                OPC-UA username. Keep it set to None if the username is not
                required.
            username_env_var (str | None):
                Environment variable which contains the OPC-UA username.
            password (str | None):
                OPC-UA password. Keep it set to None if the password is not
                required.
            password_env_var (str | None):
                Environment variable which contains the OPC-UA password.
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
        self._security_policy: str | None = security_policy
        self._client: AsyncuaClient | None = None
        self._host_name: str = (
            host_name if host_name is not None else socket.gethostname()
        )
        self._client_app_uri: str = (
            client_app_uri
            if client_app_uri is not None
            else f"urn:{self._host_name}:foobar:myselfsignedclient"
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

        self._private_key_file_path: Path = (
            Path(private_key_file_path)
            if private_key_file_path is not None
            else Path("private.selfsigned.pem")
        )
        self._certificate_file_path: Path = (
            Path(certificate_file_path)
            if certificate_file_path is not None
            else Path("cert.selfsigned.der")
        )

        if not isinstance(trust_store_certificates_paths, list | None):
            raise TypeError(
                f"Connector '{name}': trust_store_certificates_paths, when "
                f"defined, must be a list of strings"
            )

        self._trust_store_certificates_paths: list[Path] = []
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
                self._trust_store_certificates_paths.append(
                    trust_store_cert_path
                )

    @property
    def security_policy(self) -> str | None:
        """Returns the security policy used by the connector."""
        return self._security_policy

    @property
    def host_name(self) -> str:
        """Returns the host name used by the connector."""
        return self._host_name

    @property
    def client_app_uri(self) -> str:
        """Returns the client application URI used by the connector."""
        return self._client_app_uri

    @property
    def private_key_file_path(self) -> Path | None:
        """Returns the path to the private key file."""
        return self._private_key_file_path

    @property
    def certificate_file_path(self) -> Path | None:
        """Returns the path to the certificate file."""
        return self._certificate_file_path

    @override
    async def _async_connect(self) -> bool:
        """Async function which uses the asyncua library to connect to the
        OPC-UA server.

        Returns:
            bool:
                True if the client is connected to the server.
        """
        url = f"opc.tcp://{self.ip}:{self.port}"
        _logger.debug(
            f"Connecting '{self.name}' connector to OPC-UA server. Url is: "
            f"{url}"
        )
        _logger.debug(
            f"Setting up the certificates for the '{self.name}' connector."
        )

        try:
            await setup_self_signed_certificate(
                self._private_key_file_path,
                self._certificate_file_path,
                self._client_app_uri,
                self._host_name,
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
        client.application_uri = self._client_app_uri

        if self._username:
            client.set_user(self._username)

        if self._password:
            client.set_password(self._password)

        security_policy = _security_policy_string_to_asyncua_policy(
            self._security_policy
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

        if len(self._trust_store_certificates_paths) > 0:
            trust_store = TrustStore(self._trust_store_certificates_paths, [])
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

        self._client = client
        try:
            await self._client.connect()
        except Exception as e:
            _logger.debug(
                f"Couldn't connect the '{self.name}' connector to the OPC-UA "
                f"server"
            )
            _logger.error(e)
            return False
        _logger.debug(
            f"Connected the '{self.name}' connector to the OPC-UA server"
        )
        return True

    @override
    async def _async_disconnect(self) -> bool:
        """Async function which uses the asyncua library to disconnect from the
        OPC-UA server.

        Returns:
            bool:
                True if the client is disconnected from the server.
        """
        _logger.debug(
            f"Disconnecting '{self.name}' connector from OPC-UA server"
        )
        if self._client is None:
            _logger.debug(
                f"The '{self.name}' connector was already disconnected"
            )
            return True

        try:
            await self._client.disconnect()
        except Exception as e:
            _logger.debug(f"Couldn't disconnect '{self.name}' connector")
            _logger.error(e)
            return False

        _logger.debug(f"Disconnected '{self.name}' connector")
        return True

    @override
    async def _async_get_remote_node(self, path: str) -> asyncua.Node | None:
        """Asynchronous function which returns the node from the OPC-UA server.

        Args:
            path (str):
                Node's path.

        Returns:
            asyncua.Node | None:
                The node from the OPC-UA server if it exists, None otherwise.
        """
        _logger.debug(f"Retrieving node '{path}' from OPC-UA server")

        if self._client is None:
            raise Exception(
                f"Couldn't retrieve remote node '{path}' using '{self._name}' "
                f"connector: the client is not connected"
            )

        node = None
        try:
            if path.startswith("ns"):
                # path is a node id
                node = self._client.get_node(path)
            else:
                node = await self._client.get_root_node().get_child(path)
            assert isinstance(
                node, asyncua.Node
            ), "Node read by remote OPC-UA server must be an asyncua.Node"
            _logger.debug(f"Retrieved node '{path}' successfully")
        except UaError as exp:
            _logger.error(exp)

        return node

    @override
    async def _async_read_node_value(self, path: str) -> Any:
        """Asynchronously reads the node's value from the server.

        Args:
            path (str):
                Node's path.

        Returns:
            Any:
                Value read from the server.
        """
        _logger.debug(f"Reading node '{path}'")
        node = await self._async_get_remote_node(path)
        if node is None:
            raise ValueError(
                f"Couldn't read value of '{path}' using the '{self.name}' "
                f"connector: the node does not exist"
            )
        value = await node.get_value()
        _logger.debug(f"Read node '{path}'. Its value is: {value!r}")
        return value

    @override
    async def _async_write_node_value(self, path: str, value: Any) -> bool:
        """Function which asynchronously writes the value to the OPC-UA server.

        Args:
            path (str):
                Node's path.
            value (Any):
                Value to write to the server.

        Returns:
            bool:
                True if the value was written successfully.
        """
        _logger.debug(f"Writing node '{path}' with value: {value}")

        node = await self._async_get_remote_node(path)
        if node is None:
            raise ValueError(
                f"Couldn't read value of '{path}' using the '{self.name}' "
                f"connector: the node does not exist"
            )

        success = True
        try:
            current_value = await node.read_data_value()
            current_value_type = current_value.Value.VariantType
            _logger.debug(
                f"Overriding node '{path}', which previously had value "
                f"{current_value!r} (type {current_value_type}), with value: "
                f"{value!r}"
            )
            await node.write_value(value, current_value_type)
        except UaError as exp:
            _logger.error(exp)
            success = False

        _logger.debug(f"Written node '{path}' with value: {value}")
        return success

    @override
    async def _async_call_node_as_method(
        self, path: str, kwargs: dict[str, Any]
    ) -> Any:
        """Asynchronously calls the method at path <path> with <kwargs> as its
        arguments.

        Args:
            path (str):
                Node/method path.
            kwargs (dict[str, Any]):
                Method arguments expressed as key/name - value pairs.

        Returns:
            Any:
                Method's returned value.
        """
        _logger.debug(
            f"Calling remote method '{path}', with the following parameters: "
            f"{kwargs}"
        )
        if self._client is None:
            raise Exception(
                f"Couldn't call remote method '{path}' using '{self._name}' "
                f"connector: the client is not connected"
            )

        node = await self._async_get_remote_node(path)
        if node is None:
            raise ValueError(
                f"Couldn't call remote method '{path}' using '{self._name}' "
                f"connector: the node doesn't exist"
            )

        # check if the node has inputs
        method_inputs = await get_input_arguments(node)
        inputs = []
        if method_inputs is not None:
            inputs = (
                await method_inputs.read_value()
            )  # returns a list of Argument-Class
            assert isinstance(inputs, list), "inputs must be a list"

        params = []
        for ua_param, value in zip(inputs, kwargs.values(), strict=False):
            dt = ua_param.DataType
            identifier = dt.Identifier
            variant_type = VariantType(identifier)
            params.append(asyncua.ua.Variant(value, variant_type))

        _logger.debug(
            f"Converted parameters of '{path}' into VariantTypes: {params}"
        )

        result = None
        try:
            parent = await node.get_parent()
            result = await parent.call_method(node.nodeid, *params)
            _logger.debug(
                f"Called '{path}' using the parent node. "
                f"Return value is: {result!r}"
            )
        except UaError as exp:
            _logger.error(exp)
        return result

    @override
    async def _async_subscribe_to_node_changes(
        self,
        path: str,
        callback: Callable[[Any, OpcuaSubscriptionArguments], None],
    ) -> int:
        """Asynchronous function which subscribes to remote variable data
        changes.

        Args:
            path (str):
                Node path.
            callback (Callable[[Any, SubscriptionArguments], None]):
                Subscription's callback. The first parameter is the new value,
                while the second parameter is additional data that is protocol
                dependent.

        Returns:
            int:
                Handler code which can be used to unsubscribe from new events.
        """
        _logger.debug(f"Subscribing to remote node '{path}'")
        if self._client is None:
            raise Exception(
                f"Couldn't subscribe to '{path}': Client is not running inside "
                f"the '{self._name}' connector"
            )

        handler = OpcUaDataChangeHandler(callback)
        subscription = await self._client.create_subscription(1, handler)
        node = await self._async_get_remote_node(path)

        if node is None:
            raise Exception(
                f"Couldn't subscribe to unexisting node '{path}' using the "
                f"'{self._name}' connector"
            )

        res = await subscription.subscribe_data_change(node)
        assert isinstance(res, int), "subscription handler must be a int"
        _logger.debug(
            f"Subscribed to remote node '{path}'. "
            f"Subscription handler code: {res}"
        )
        return res

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

    def __repr__(self) -> str:
        return self.__str__()


class OpcUaDataChangeHandler(DataChangeNotificationHandler):  # type: ignore[misc]
    """Handles OPC-UA data changes by calling a callback function."""

    def __init__(
        self, callback: Callable[[Any, OpcuaSubscriptionArguments], None]
    ) -> None:
        """Stores the callback to be called when a remote value changes.

        Args:
            callback (Callable[[Any, OpcuaSubscriptionArguments], None]):
                Callback function to be called when a remote value changes.
        """
        self._callback = callback

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


class OpcuaRemoteResourceSpec(RemoteResourceSpec):
    """Represents node properties that are specific for the OPC UA protocol."""

    def __init__(
        self,
        parent: "DataModelNode | None" = None,
        remote_path: str | None = None,
        node_id: str | None = None,
        namespace: str | None = None,
    ) -> None:
        """Constructor.

        Args:
            parent (DataModelNode, optional):
                Node which owns these properties.
            remote_path (str, optional):
                Node's path on the remote OPC UA server.
            node_id (str, optional):
                Node's id on the remote OPC UA server.
            namespace (str, optional):
                Node's namespace on the remote OPC UA server.
        """
        super().__init__(parent=parent, remote_path=remote_path)
        self._node_id: str | None = node_id
        self._namespace: str | None = namespace

    @override
    def remote_path(self) -> str | None:
        """Returns the 'remote_path' used to interact with the node on the
        server.

        Returns:
            str | None:
                Path used to interact with the node on the server.
        """
        if self._remote_path is not None:
            return self._remote_path

        if self._node_id is not None:
            return self._node_id

        if self._parent:
            remote_path = ""
            if self._parent.parent:
                parent_remote_path = self._parent.parent.remote_path
                remote_path = parent_remote_path if parent_remote_path else ""
            if self._namespace:
                return (
                    remote_path
                    + "/"
                    + self._namespace
                    + ":"
                    + self._parent.name
                )
            else:
                return remote_path + "/" + self._parent.name

        return None

    @override
    def inheritable_spec(self) -> "OpcuaRemoteResourceSpec":
        """Returns a copy of this object, where the only properties that get
        copied are properties that will be inherited by child nodes.

        Returns:
            OpcuaRemoteResourceSpec:
                Object with inheritable properties.
        """
        return OpcuaRemoteResourceSpec(namespace=self._namespace)

    @override
    def merge_specs(
        self,
        spec1: "OpcuaRemoteResourceSpec",
        spec2: "OpcuaRemoteResourceSpec",
    ) -> "OpcuaRemoteResourceSpec":
        """Creates a third object which has the combined properties of spec1 and
        spec2.
        > Note that spec1 has priority over spec2: spec1's properties override
        spec2's properties when the properties are defined for both objects.

        Args:
            spec1 (OpcuaRemoteResourceSpec):
                First object to be merged.
            spec2 (OpcuaRemoteResourceSpec):
                Second object to be merged.

        Returns:
            OpcuaRemoteResourceSpec:
                Object with merged properties of both spec1 and spec2.
        """
        assert isinstance(
            spec1, OpcuaRemoteResourceSpec
        ), "spec1 must be a OpcuaRemoteResourceSpec"
        assert isinstance(
            spec2, OpcuaRemoteResourceSpec
        ), "spec2 must be a OpcuaRemoteResourceSpec"
        new_spec = OpcuaRemoteResourceSpec()
        new_spec._parent = spec1._parent if spec1._parent else spec2._parent
        new_spec._remote_path = (
            spec1._remote_path if spec1._remote_path else spec2._remote_path
        )
        new_spec._node_id = spec1._node_id if spec1._node_id else spec2._node_id
        new_spec._namespace = (
            spec1._namespace if spec1._namespace else spec2._namespace
        )
        return new_spec

    def __str__(self) -> str:
        return (
            "OpcuaRemoteResourceSpec("
            f"remote_path={self.remote_path!r}, "
            f"node_id={self._node_id!r}, "
            f"namespace={self._namespace!r}"
            ")"
        )

    def __repr__(self) -> str:
        return self.__str__()
