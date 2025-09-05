from dataclasses import dataclass
import logging
import socket
from pathlib import Path
from typing import Any, Callable

import asyncua
from asyncua import Client as AsyncuaClient
from asyncua.common.subscription import DataChangeNotificationHandler, DataChangeNotif
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto.security_policies import (
    SecurityPolicyBasic256Sha256,
    SecurityPolicy,
)
from asyncua.crypto.truststore import TrustStore
from asyncua.crypto.validator import CertificateValidator, CertificateValidatorOptions
from asyncua.ua import UaError, VariantType
from cryptography.x509.oid import ExtendedKeyUsageOID
from typing_extensions import override

from machine_data_model.nodes.connectors.abstract_connector import (
    AbstractConnector,
    SubscriptionArguments,
)

logging.basicConfig(level=logging.ERROR)
_logger = logging.getLogger(__name__)

USE_TRUST_STORE = False


@dataclass(frozen=True)
class OpcuaSubscriptionArguments(SubscriptionArguments):
    """
    Data returned to the OPC-UA subscription callback.
    """

    node: asyncua.Node
    value: Any
    notification: DataChangeNotif


def _security_policy_string_to_asyncua_policy(
    policy_string: str | None,
) -> type[SecurityPolicy] | None:
    """
    Converts a string containing the desired security policy into a asyncua SecurityPolicy type.
    """
    policy: type[SecurityPolicy] | None = None
    if policy_string == "SecurityPolicyBasic256Sha256":
        policy = SecurityPolicyBasic256Sha256

    return policy


class OpcuaConnector(AbstractConnector):
    """
    Represents an OPCUA client
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        ip: str | None = None,
        port: int | None = None,
        security_policy: str | None = None,
        host_name: str | None = None,
        client_app_uri: str | None = None,
        private_key_file_path: str | None = None,
        certificate_file_path: str | None = None,
    ) -> None:
        """
        Initializes an OPCUA client.

        :param id: node ID
        :param name: client name
        :param ip: OPC-UA server address
        :param port: OPC-UA server port
        :param security_policy: OPC-UA security mode
        :param host_name: host name
        :param client_app_uri: app URI
        :param private_key_file_path: path to the private key file
        :param certificate_file_path: path to the certificate file
        """
        super().__init__(id=id, name=name, ip=ip, port=port)
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

    @property
    def security_policy(self) -> str | None:
        return self._security_policy

    @property
    def host_name(self) -> str:
        return self._host_name

    @property
    def client_app_uri(self) -> str:
        return self._client_app_uri

    @property
    def private_key_file_path(self) -> Path | None:
        return self._private_key_file_path

    @property
    def certificate_file_path(self) -> Path | None:
        return self._certificate_file_path

    @override
    def connect(self) -> bool:
        """
        Connect to the OPC-UA server.

        :return: True if the client is connected to the server
        """
        success = self._handle_task(self._async_connect())
        return success

    async def _async_connect(self) -> bool:
        """
        Async function which uses the asyncua library to connect to the OPC-UA server.

        :return: True if the client is connected to the server
        """
        url = "opc.tcp://{}:{}".format(self.ip, self.port)

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

        security_policy = _security_policy_string_to_asyncua_policy(
            self._security_policy
        )

        if security_policy is not None:
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

        # TODO: handle trust store
        if USE_TRUST_STORE:
            trust_store = TrustStore(
                [Path("examples") / "certificates" / "trusted" / "certs"], []
            )
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
            _logger.error(e)
            return False
        return True

    @override
    def disconnect(self) -> bool:
        """
        Disconnect from the OPC-UA server.

        :return: True if the client is disconnected from the server
        """
        success = self._handle_task(self._async_disconnect())
        return success

    async def _async_disconnect(self) -> bool:
        """
        Async function which uses the asyncua library to disconnect from the OPC-UA server.

        :return: True if the client is disconnected from the server
        """
        if self._client is None:
            return True

        try:
            await self._client.disconnect()
        except Exception as e:
            _logger.error(e)
            return False

        return True

    @override
    def _get_remote_node(self, path: str) -> asyncua.Node | None:
        """
        Returns the node from the OPC-UA server,
        The node's type is asyncua.Node.
        """
        get_node_coroutine = self._async_get_remote_node(path)
        task_result: asyncua.Node | None = self._handle_task(get_node_coroutine)
        assert isinstance(
            task_result, (asyncua.Node, type(None))
        ), "Node read by remote OPC-UA server must be an asyncua.Node"
        return task_result

    async def _async_get_remote_node(self, path: str) -> asyncua.Node | None:
        """
        Asynchronous function which returns the node from the OPC-UA server.
        """
        node = None
        if self._client is None:
            return None
        try:
            node = await self._client.get_root_node().get_child(path)
        except UaError as exp:
            _logger.error(exp)

        return node

    @override
    def read_node_value(self, path: str) -> Any:
        """
        Reads the node's value and returns it.
        """
        value = self._handle_task(self._async_read_node_value(path))
        return value

    async def _async_read_node_value(self, path: str) -> Any:
        """
        Asynchronously reads the node's value from the server.
        """
        node = await self._async_get_remote_node(path)
        if node is None:
            raise ValueError(
                f"Couldn't read value of '{path}' using the {self.name} connector: the node does not exist"
            )
        value = await node.get_value()
        return value

    @override
    def write_node_value(self, path: str, value: Any) -> bool:
        """
        Writes a value to the remote OPC-UA server.
        """
        node = self._get_remote_node(path)
        assert isinstance(
            node, (asyncua.Node, type(None))
        ), "Node read by remote OPC-UA server must be an asyncua.Node"
        if node is None:
            return False

        success = self._handle_task(self._async_write_node_value(node, value))
        return success

    async def _async_write_node_value(self, node: asyncua.Node, new_value: Any) -> bool:
        """
        Function which asynchronously writes the value to the OPC-UA server-
        """
        success = True
        try:
            current_value = await node.read_data_value()
            current_value_type = current_value.Value.VariantType
            await node.write_value(new_value, current_value_type)
        except UaError as exp:
            _logger.error(exp)
            success = False
        return success

    @override
    def call_node_as_method(self, path: str, kwargs: dict[str, Any]) -> Any:
        """
        Calls the method at path <path> with <kwargs> as its arguments.

        :param path: node/method path
        :param kwargs: method arguments expressed as key/name - value pairs
        :return: dict of results in the form of name - value pairs
        """
        result = self._handle_task(self._async_call_node_as_method(path, **kwargs))
        return result

    async def _async_call_node_as_method(
        self, path: str, **kwargs: dict[str, Any]
    ) -> Any:
        """
        Asynchronously calls the method at path <path> with <kwargs> as its arguments.

        :param path: node/method path
        :param kwargs: method arguments expressed as key/name - value pairs
        :return: dict of results in the form of name - value pairs
        """
        if self._client is None:
            return None

        node = await self._async_get_remote_node(path)
        if node is None:
            raise ValueError("Couldn't call remote method: the node doesn't exist")
        path_parts = path.lstrip("/").split("/")
        input_arg_path = path + "/InputArguments"
        method_inputs = await self._async_get_remote_node(input_arg_path)
        inputs = []
        if method_inputs is not None:
            inputs = (
                await method_inputs.read_value()
            )  # returns a list of Argument-Class
            assert isinstance(inputs, list), "inputs must be a list"

        # Try to convert the parameters types from python types to the equivalent asyncua VariantTypes
        params = []
        for ua_param, value in zip(inputs, kwargs.values()):
            dt = ua_param.DataType
            identifier = dt.Identifier
            variant_type = VariantType(identifier)
            params.append(asyncua.ua.Variant(value, variant_type))

        if len(path_parts) == 0:
            return None

        if len(path_parts) == 1:
            method_id = path_parts[0]
            result = await self._client.get_root_node().call_method(method_id, *params)
            return result

        result = None
        try:
            parent_path = "/".join(path_parts[:-1])
            method_id = path_parts[-1]
            parent_node = await self._async_get_remote_node(parent_path)
            if parent_node:
                result = await parent_node.call_method(method_id, *params)
        except UaError as exp:
            _logger.error(exp)
        return result

    @override
    def subscribe_to_node_changes(
        self, path: str, callback: Callable[[Any, OpcuaSubscriptionArguments], None]
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
        return self._handle_task(self._async_subscribe_to_node_changes(path, callback))

    async def _async_subscribe_to_node_changes(
        self, path: str, callback: Callable[[Any, OpcuaSubscriptionArguments], None]
    ) -> int:
        """
        Asynchronous function which subscribes to remote variable data changes.

        :param path: node path
        :param callback: callback
        :return: handler code which can be used to unsubscribe from new events
        """
        if self._client is None:
            raise Exception("Client is not running")

        handler = OpcUaDataChangeHandler(callback)
        subscription = await self._client.create_subscription(1, handler)
        node = await self._async_get_remote_node(path)

        if node is None:
            raise Exception("Couldn't subscribe to unexisting node")

        res = await subscription.subscribe_data_change(node)
        assert isinstance(res, int), "subscription handler must be a int"
        return res

    def __str__(self) -> str:
        return (
            "OpcuaConnector("
            f"name={repr(self.name)}, "
            f"id={repr(self.id)}, "
            f"ip={repr(self.ip)}, "
            f"port={repr(self.port)}, "
            f"security_policy={repr(self.security_policy)}, "
            f"host_name={repr(self.host_name)}, "
            f"client_app_uri={repr(self.client_app_uri)}, "
            f"private_key_file_path={repr(self.private_key_file_path)}, "
            f"certificate_file_path={repr(self.certificate_file_path)}"
            ")"
        )

    def __repr__(self) -> str:
        return self.__str__()


class OpcUaDataChangeHandler(DataChangeNotificationHandler):  # type: ignore[misc]
    """
    Handles OPC-UA data changes by calling a callback function.
    """

    def __init__(
        self, callback: Callable[[Any, OpcuaSubscriptionArguments], None]
    ) -> None:
        """
        Stores the callback to be called when a remote value changes.
        """
        self._callback = callback

    def datachange_notification(
        self, node: asyncua.Node, val: Any, data: DataChangeNotif
    ) -> None:
        """
        called for every datachange notification from server
        """
        other = OpcuaSubscriptionArguments(node=node, value=val, notification=data)
        self._callback(val, other)
