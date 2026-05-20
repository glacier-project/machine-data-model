"""Tests for the data model builder that exercise connector classes.

Lives in its own file so the no-extras CI job can ignore it.
"""

import pytest

pytest.importorskip("asyncua")
pytest.importorskip("aiomqtt")

from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from machine_data_model.builder.data_model_builder import (  # noqa: E402
    _register_yaml_constructors,
)
from machine_data_model.nodes.connectors.mqtt import (  # noqa: E402
    MqttConnector,
    MqttRemoteResourceSpec,
)
from machine_data_model.nodes.connectors.opcua.opcua_connector import (  # noqa: E402
    OpcuaConnector,
    OpcuaRemoteResourceSpec,
)


class TestDataModelBuilderConnectors:
    def setup_method(self) -> None:
        _register_yaml_constructors()

    def test_build_opcua_connector_minimal(self) -> None:
        """
        Test OpcuaConnector build from YAML with minimal configuration.

        Verify that the connector is correctly constructed with default values.
        """
        yaml_content = """
            !!OpcuaConnector
            name: "opcua_server"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaConnector)
        assert node.name == "opcua_server"
        assert node.ip == "127.0.0.1"
        assert node.port == 4840

    def test_build_opcua_connector_full(self) -> None:
        """
        Test OpcuaConnector build from YAML with full configuration.

        Verify that all parameters are correctly parsed.
        """
        yaml_content = """
            !!OpcuaConnector
            name: "opcua_server"
            ip: "192.168.1.100"
            port: 4841
            security_policy: "SecurityPolicyBasic256Sha256"
            host_name: "myhost"
            client_app_uri: "urn:myapp"
            certificate_file_path: "/path/to/cert.pem"
            private_key_file_path: "/path/to/key.pem"
            username: "user"
            password: "pass"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaConnector)
        assert node.name == "opcua_server"
        assert node.ip == "192.168.1.100"
        assert node.port == 4841
        assert node.security_policy == "SecurityPolicyBasic256Sha256"
        assert node.host_name == "myhost"
        assert node.client_app_uri == "urn:myapp"
        assert node.certificate_file_path == Path("/path/to/cert.pem")
        assert node.private_key_file_path == Path("/path/to/key.pem")

    def test_build_opcua_connector_with_env_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Test OpcuaConnector build from YAML with environment variable
        references.

        Verify that environment variable parameters correctly override direct
        values.

        Args:
            monkeypatch (pytest.MonkeyPatch):
                Pytest fixture for setting environment variables.
        """
        # Set environment variables
        monkeypatch.setenv("OPCUA_IP", "10.0.0.1")
        monkeypatch.setenv("OPCUA_PORT", "5000")

        yaml_content = """
            !!OpcuaConnector
            name: "opcua_server"
            ip: "192.168.1.100"
            ip_env_var: "OPCUA_IP"
            port: 4841
            port_env_var: "OPCUA_PORT"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaConnector)
        assert node.name == "opcua_server"
        # Env vars override the direct values
        assert node.ip == "10.0.0.1"
        assert node.port == 5000

    def test_build_opcua_remote_resource_spec_with_remote_path(self) -> None:
        """
        Test OpcuaRemoteResourceSpec build from YAML with remote_path.

        Verify that remote_path is correctly parsed.
        """
        yaml_content = """
            !!OpcuaRemoteResourceSpec
            remote_path: "ns=2;s=MyNode"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaRemoteResourceSpec)
        assert node.remote_path == "ns=2;s=MyNode"
        assert node.node_id is None
        assert node.namespace is None

    def test_build_opcua_remote_resource_spec_with_node_id(self) -> None:
        """
        Test OpcuaRemoteResourceSpec build from YAML with node_id.

        Verify that node_id is correctly parsed.
        """
        yaml_content = """
            !!OpcuaRemoteResourceSpec
            node_id: "i=12345"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaRemoteResourceSpec)
        assert node.node_id == "i=12345"
        assert node.remote_path is None

    def test_build_opcua_remote_resource_spec_with_namespace(self) -> None:
        """
        Test OpcuaRemoteResourceSpec build from YAML with namespace.

        Verify that namespace is correctly parsed.
        """
        yaml_content = """
            !!OpcuaRemoteResourceSpec
            namespace: "2"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaRemoteResourceSpec)
        assert node.namespace == "2"

    def test_build_opcua_remote_resource_spec_with_parent_resource_spec(
        self,
    ) -> None:
        """
        Test OpcuaRemoteResourceSpec build from YAML with parent_resource_spec.

        Verify that parent_resource_spec is correctly parsed.
        """
        yaml_content = """
            !!OpcuaRemoteResourceSpec
            node_id: "ns=6;s=Scalar_Static_Boolean"
            parent_node_id: "ns=6;s=Methods"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaRemoteResourceSpec)
        assert node.parent_node_id == "ns=6;s=Methods", (
            "Got:",
            " {node.parent_node_id} expected: ns=6;s=Methods",
        )
        assert isinstance(node, OpcuaRemoteResourceSpec)
        assert node.remote_path is None, f"Got: {node.remote_path} expected: ''"
        assert (
            node.node_id == "ns=6;s=Scalar_Static_Boolean"
        ), f"Got: {node.node_id} expected: ns=6;s=Scalar_Static_Boolean"
        assert node.namespace is None, f"Got: {node.namespace} expected: None"
        assert node.parent_node_id == "ns=6;s=Methods"

    def test_build_opcua_remote_resource_spec_full(self) -> None:
        """
        Test OpcuaRemoteResourceSpec build from YAML with all parameters.

        Verify that all parameters are correctly parsed.
        """
        yaml_content = """
            !!OpcuaRemoteResourceSpec
            remote_path: "ns=2;s=MyNode"
            node_id: "i=12345"
            namespace: "2"
            parent_node_id: "ns=6;s=Methods"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, OpcuaRemoteResourceSpec)
        # remote_path takes precedence when defined
        assert node.remote_path == "ns=2;s=MyNode"
        assert node.node_id == "i=12345"
        assert node.namespace == "2"
        assert node.parent_node_id == "ns=6;s=Methods"

    def test_build_mqtt_connector_minimal(self) -> None:
        yaml_content = """
            !!MqttConnector
            name: "mqtt_broker"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, MqttConnector)
        assert node.name == "mqtt_broker"
        assert node.ip == "127.0.0.1"
        assert node.port == 1883
        assert node.qos == 0
        assert not node.retain

    def test_build_mqtt_connector_full(self) -> None:
        yaml_content = """
            !!MqttConnector
            name: "mqtt_broker"
            ip: "192.168.1.10"
            port: 1884
            username: "user"
            password: "pass"
            client_id: "machine-data-model"
            topic_prefix: "machines/boiler-1"
            keepalive: 30
            qos: 1
            retain: true
            payload_codec: "json"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, MqttConnector)
        assert node.name == "mqtt_broker"
        assert node.ip == "192.168.1.10"
        assert node.port == 1884
        assert node.username == "user"
        assert node.password == "pass"
        assert node.client_id == "machine-data-model"
        assert node.topic_prefix == "machines/boiler-1"
        assert node.keepalive == 30
        assert node.qos == 1
        assert node.retain
        assert node.payload_codec == "json"

    def test_build_mqtt_remote_resource_spec_full(self) -> None:
        yaml_content = """
            !!MqttRemoteResourceSpec
            remote_path: "legacy/topic"
            topic: "plant/line-1/temp"
            topic_prefix: "machines/boiler-1"
            subscribe_topic: "plant/line-1/temp/state"
            publish_topic: "plant/line-1/temp/set"
            qos: 2
            retain: true
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, MqttRemoteResourceSpec)
        assert node.remote_path == "legacy/topic"
        assert node.topic == "plant/line-1/temp"
        assert node.topic_prefix == "machines/boiler-1"
        assert node.subscribe_topic == "plant/line-1/temp/state"
        assert node.publish_topic == "plant/line-1/temp/set"
        assert node.qos == 2
        assert node.retain
