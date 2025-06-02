import logging
import socket
from pathlib import Path
from typing import Any

import asyncua
from asyncua import Client as AsyncuaClient
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

from machine_data_model.nodes.connectors.abstract_connector import AbstractConnector
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
    VariableNode,
)

logging.basicConfig(level=logging.ERROR)
_logger = logging.getLogger(__name__)

USE_TRUST_STORE = False


async def _convert_asyncua_node_to_data_model_node(
    node: asyncua.Node,
) -> DataModelNode | None:
    """
    Converts an asyncua.Node to a DataModelNode.
    """
    variant_type = await node.read_data_type_as_variant_type()

    name_text = None
    try:
        name = await node.read_display_name()
        name_text = name.Text
    except UaError:
        pass

    description_text = None
    try:
        description = await node.read_description()
        description_text = description.Text
    except UaError:
        pass

    if variant_type in [
        VariantType.Int16,
        VariantType.Int32,
        VariantType.Int64,
        VariantType.Float,
        VariantType.Double,
        VariantType.UInt16,
        VariantType.UInt32,
        VariantType.UInt64,
    ]:
        value = await node.get_value()
        assert isinstance(value, (int, float)), "Value must be numeric"
        return NumericalVariableNode(
            name=name_text,
            value=value,
            description=description_text,
        )

    if variant_type in [VariantType.String, VariantType.ByteString]:
        value = await node.get_value()
        assert isinstance(value, str), "Value must be a string"
        return StringVariableNode(
            name=name_text,
            value=value,
            description=description_text,
        )
    return None


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
    ):
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
        self._private_key_file_path: Path | None = (
            Path(private_key_file_path) if private_key_file_path is not None else None
        )
        self._certificate_file_path: Path | None = (
            Path(certificate_file_path) if certificate_file_path is not None else None
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
    def connect(self) -> None:
        """
        Connect to the OPC-UA server.
        """
        self._handle_task(self._async_connect())

    async def _async_connect(self) -> None:
        """
        Async function which uses the asyncua library to connect to the OPC-UA server.
        """
        url = "opc.tcp://{}:{}".format(self.ip, self.port)

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
        client = AsyncuaClient(url=url)
        client.application_uri = self._client_app_uri

        if self._security_policy is not None:
            await client.set_security(
                _security_policy_string_to_asyncua_policy(self._security_policy),
                certificate=self.certificate_file_path,
                private_key=self.private_key_file_path,
                server_certificate=None,  # "certificate-example.der",
            )

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
        await self._client.connect()

    @override
    def disconnect(self) -> None:
        """
        Disconnect from the OPC-UA server.
        """
        self._handle_task(self._async_disconnect())

    async def _async_disconnect(self) -> None:
        """
        Async function which uses the asyncua library to disconnect from the OPC-UA server.
        """
        if self._client is None:
            return

        await self._client.disconnect()

    @override
    def get_data_model_node(
        self, path: str, stub_node: DataModelNode | None = None
    ) -> DataModelNode | None:
        """
        Returns the node from the OPC-UA server,
        converted into a DataModelNode.
        """
        asyncua_node = self._get_remote_node(path)
        assert isinstance(
            asyncua_node, (asyncua.Node, type(None))
        ), "Node read by remote OPC-UA server must be an asyncua.Node"
        if asyncua_node is None:
            return None

        data_model_node = self._handle_task(
            _convert_asyncua_node_to_data_model_node(asyncua_node)
        )
        if data_model_node is None:
            return None

        if stub_node is None:
            return data_model_node

        # TODO: it might be a cleaner approach to return the information
        #       retrieved from the server and modify the original node later
        #       instead of returning a new node
        data_model_node.set_remote_path(stub_node.remote_path)
        data_model_node.set_connector(stub_node.connector)
        data_model_node.set_connector_name(stub_node.connector_name)

        if stub_node.name:
            data_model_node.set_name(stub_node.name)

        if stub_node.description:
            data_model_node.set_description(stub_node.description)

        return data_model_node

    def _get_remote_node(self, path: str) -> Any:
        """
        Returns the node from the OPC-UA server,
        The node's type is asyncua.Node.
        """
        get_node_coroutine = self._async_get_remote_node(path)
        task_result = self._handle_task(get_node_coroutine)
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
        node = self.get_data_model_node(path)
        if not isinstance(node, VariableNode):
            return None
        return node.value

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
