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
    - !!FolderNode
      name: "4:Boilers"
      description: "Boilers folder"
      children:
        - !!ObjectVariableNode
          name: "4:Boiler #2"
          description: "Boiler 2"
          properties:
            - !!StringVariableNode
              name: "2:AssetId"
              description: "asset id"

            - !!ObjectVariableNode
              name: "2:ParameterSet"
              description: "parameter set"
              properties:
                - !!NumericalVariableNode
                  name: "4:CurrentTemperature"
                  description: "current temperature"
                - !!NumericalVariableNode
                  name: "4:OverheatedThresholdTemperature"
                  description: "overheated threshold temp"
    - !!FolderNode
      name: "3:OpcPlc"
      description: "Opc PLC"
      children:
        - !!FolderNode
          name: "3:Methods"
          description: "methods"
          children:
            - !!MethodNode
              name: "4:HeaterOff"
              description: "heater off"
            - !!MethodNode
              name: "4:HeaterOn"
              description: "heater on"

    - !!FolderNode
      name: "6:ReferenceTest"
      description: "Reference Test"
      children:
        - !!FolderNode
          name: "6:Methods"
          description: "Reference Test Methods"
          children:
            - !!MethodNode
              name: "6:Methods_Add"
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
        - !!FolderNode
          name: "6:Scalar"
          description: "Scalars"
          children:
            - !!FolderNode
              name: "6:Scalar_Static"
              description: "Static Scalars"
              children:
                - !!BooleanVariableNode
                  name: "6:Scalar_Static_Boolean"
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
        node = dm.get_node("Objects/4:Boilers/4:Boiler #2/2:AssetId")
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
            "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/4:OverheatedThresholdTemperature"
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
            "Objects/6:ReferenceTest/6:Scalar/6:Scalar_Static/6:Scalar_Static_Boolean"
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
            "Objects/6:ReferenceTest/6:Scalar/6:Scalar_Static/6:Scalar_Static_Boolean"
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
            "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/4:OverheatedThresholdTemperature"
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
        node = dm.get_node("Objects/6:ReferenceTest/6:Methods/6:Methods_Add")
        assert isinstance(node, MethodNode), "the node should be defined"
        result = node(2.0, 3)
        result = result.return_values["AddResult"]
        assert isinstance(result, float), "the result should be a floating point number"
        assert math.isclose(result, 5), "the result should be equal to 2.0 + 3 = 5"
        dm.close_connectors()
