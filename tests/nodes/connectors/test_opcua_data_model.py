import math
import socket
from typing import Tuple

import pytest
from docker.models.containers import Container

from machine_data_model.data_model import DataModel
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import VariableNode

yaml_template = """
name: "boiler"
machine_category: "boiler_cat"
machine_type: "boiler_type"
machine_model: "boiler_model"
description: "boiler description"
connectors:
  - !!OpcuaConnector
    name: "myOpcuaConnector1"
    ip: "127.0.0.1"
    port: {opcua_port}
    security_policy: "SecurityPolicyBasic256Sha256"
root:
  !!FolderNode
  name: "Objects"
  description: "Objects folder"
  connector_name: "myOpcuaConnector1"
  children:
    - !!MethodNode
      name: "Methods_Output_With_Node_Id"
      description: "OPC-UA nodes can also specify the node_id to access the remote node"
      remote_resource_spec:
        !!OpcuaRemoteResourceSpec
        node_id: "ns=6;s=Methods_Output"
      returns:
        - !!StringVariableNode
          name: "Result"
          description: "Method output"
    - !!MethodNode
      name: "Methods_Output_With_Remote_Path"
      remote_resource_spec:
        !!OpcuaRemoteResourceSpec
        remote_path: "/Objects/6:ReferenceTest/6:Methods/6:Methods_Output"
      description: "The remote_path overrides the qualified name. Method with no input, returns the 'Output' string"
      returns:
        - !!StringVariableNode
          name: "Result"
          description: "Method output"
    - !!FolderNode
      name: "Boilers"
      remote_resource_spec:
        !!OpcuaRemoteResourceSpec
        namespace: "4"
      description: "Boilers folder"
      children:
        - !!ObjectVariableNode
          name: "Boiler #2"
          description: "Boiler 2"
          properties:
            - !!StringVariableNode
              name: "AssetId"
              remote_resource_spec:
                !!OpcuaRemoteResourceSpec
                namespace: "2"
              description: "asset id"

            - !!ObjectVariableNode
              name: "ParameterSet"
              remote_resource_spec:
                !!OpcuaRemoteResourceSpec
                namespace: "2"
              description: "parameter set"
              properties:
                - !!NumericalVariableNode
                  name: "CurrentTemperature"
                  remote_resource_spec:
                    !!OpcuaRemoteResourceSpec
                    namespace: "4"
                  description: "current temperature"
                - !!NumericalVariableNode
                  name: "OverheatedThresholdTemperature"
                  remote_resource_spec:
                    !!OpcuaRemoteResourceSpec
                    namespace: "4"
                  description: "overheated threshold temp"
    - !!FolderNode
      name: "OpcPlc"
      remote_resource_spec:
        !!OpcuaRemoteResourceSpec
        namespace: "3"
      description: "Opc PLC"
      children:
        - !!FolderNode
          name: "Methods"
          description: "methods"
          children:
            - !!MethodNode
              name: "HeaterOff"
              remote_resource_spec:
                !!OpcuaRemoteResourceSpec
                namespace: "4"
              description: "heater off"
            - !!MethodNode
              name: "HeaterOn"
              remote_resource_spec:
                !!OpcuaRemoteResourceSpec
                namespace: "4"
              description: "heater on"

    - !!FolderNode
      name: "ReferenceTest"
      remote_resource_spec:
        !!OpcuaRemoteResourceSpec
        namespace: "6"
      description: "Reference Test"
      children:
        - !!FolderNode
          name: "Methods"
          description: "Reference Test Methods"
          children:
            - !!MethodNode
              name: "Methods_Add"
              description: "Adds a float with an integer and returns the result"
              parameters:
                - !!NumericalVariableNode
                  name: "FloatValue"
                  description: "first parameter"
                - !!NumericalVariableNode
                  name: "Uint32Value"
                  description: "second parameter"
              returns:
                - !!NumericalVariableNode
                  name: "AddResult"
                  description: "addition result"

            - !!MethodNode
              name: "Methods_Output"
              description: "Method with no input, returns the 'Output' string"
              returns:
                - !!StringVariableNode
                  name: "Result"
                  description: "Method output"

        - !!FolderNode
          name: "Scalar"
          description: "Scalars"
          children:
            - !!FolderNode
              name: "Scalar_Static"
              description: "Static Scalars"
              children:
                - !!BooleanVariableNode
                  name: "Scalar_Static_Boolean"
                  description: "Boolean node"
"""


def create_yaml_data_model(file_content: str) -> DataModel:
    """
    Uses the DataModelBuilder to create the data model starting from a string.
    """
    builder = DataModelBuilder()
    data_model = builder.from_string(file_content)
    return data_model


def free_port() -> int:
    """
    Creates a socket to get a free port number and then returns it.
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    assert isinstance(port, int), "port must be an integer"
    sock.close()
    return port


class TestOpcuaDataModel:
    def test_connector_without_name(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        yaml = """
        connectors:
          - !!OpcuaConnector
            ip: "127.0.0.1"
            port: {opcua_port}
            security_policy: "SecurityPolicyBasic256Sha256"
        """
        with pytest.raises(Exception, match="doesn't have the name attribute"):
            create_yaml_data_model(yaml.format(opcua_port=container_port))

    def test_multiple_connector_definitions(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        yaml = """
        connectors:
          - !!OpcuaConnector
            name: "myConnector"
            ip: "127.0.0.1"
            port: {opcua_port}
            security_policy: "SecurityPolicyBasic256Sha256"
          - !!OpcuaConnector
            name: "myConnector"
            ip: "127.0.0.1"
            port: {opcua_port}
            security_policy: "SecurityPolicyBasic256Sha256"
        """
        with pytest.raises(Exception, match="two connectors with the same name"):
            create_yaml_data_model(yaml.format(opcua_port=container_port))

    def test_connector_not_defined(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        yaml = """
        root:
          !!FolderNode
          name: "Objects"
          description: "Objects folder"
          connector_name: "myOpcuaConnector1"
        """
        with pytest.raises(Exception, match="not found"):
            create_yaml_data_model(yaml.format(opcua_port=container_port))

    def test_connection_failure(self) -> None:
        port = free_port()
        with pytest.raises(Exception, match="Failed to connect to the remote server"):
            create_yaml_data_model(yaml_template.format(opcua_port=port))

    def test_data_model_creation(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        assert len(dm.connectors.values()) == 1, "there should be exactly one connector"
        dm.close_connectors()

    def test_read_string_node(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        node = dm.get_node("Objects/Boilers/Boiler #2/AssetId")
        assert isinstance(node, VariableNode), "the node should be defined"
        value = node.read()
        assert isinstance(value, str), "the value should be a string"
        assert value == "Boiler #2"
        dm.close_connectors()

    def test_read_numerical_node(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        node = dm.get_node(
            "Objects/Boilers/Boiler #2/ParameterSet/OverheatedThresholdTemperature"
        )
        assert isinstance(node, VariableNode), "the node should be defined"
        value = node.read()
        assert isinstance(value, float), "the value should be a floating point number"
        dm.close_connectors()

    def test_read_boolean_node(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        node = dm.get_node(
            "Objects/ReferenceTest/Scalar/Scalar_Static/Scalar_Static_Boolean"
        )
        assert isinstance(node, VariableNode), "the node should be defined"
        value = node.read()
        assert isinstance(value, bool), "the value should be a boolean"
        dm.close_connectors()

    def test_write_boolean_node(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        node = dm.get_node(
            "Objects/ReferenceTest/Scalar/Scalar_Static/Scalar_Static_Boolean"
        )
        assert isinstance(node, VariableNode), "the node should be defined"
        prev_value = node.read()
        assert isinstance(prev_value, bool), "the prev value should be a boolean"
        success = node.write(not prev_value)
        assert success, "the value should be written successfully"
        value = node.read()
        assert isinstance(value, bool), "the new value should be a boolean"
        assert value == (
            not prev_value
        ), "the new value should be the opposite of the previous value"
        dm.close_connectors()

    def test_write_numerical_node(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        node = dm.get_node(
            "Objects/Boilers/Boiler #2/ParameterSet/OverheatedThresholdTemperature"
        )
        assert isinstance(node, VariableNode), "the node should be defined"
        prev_value = node.read()
        assert isinstance(
            prev_value, float
        ), "the value should be a floating point number"
        success = node.write(prev_value + 7)
        assert success, "the new value should be written successfully"
        new_value = node.read()
        assert isinstance(
            new_value, float
        ), "the new value should be a floating point number"
        assert math.isclose(
            new_value, prev_value + 7
        ), "the new value should be equal to the prev value +7"
        dm.close_connectors()

    def test_call_method_node(
        self,
        start_opcua_test_server: Tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        dm = create_yaml_data_model(yaml_template.format(opcua_port=container_port))
        assert dm is not None, "the data model should be defined"
        node = dm.get_node("Objects/ReferenceTest/Methods/Methods_Add")
        assert isinstance(node, MethodNode), "the node should be defined"
        result = node(2.0, 3)
        result = result.return_values["AddResult"]
        assert isinstance(result, float), "the result should be a floating point number"
        assert math.isclose(result, 5), "the result should be equal to 2.0 + 3 = 5"
        dm.close_connectors()
