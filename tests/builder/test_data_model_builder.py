import pytest
import yaml

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
    WaitConditionNode,
    WaitConditionOperator,
    WriteVariableNode,
)
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
    ReadRemoteVariableNode,
    WaitRemoteEventNode,
    WriteRemoteVariableNode,
)
from machine_data_model.builder.data_model_builder import (
    _register_yaml_constructors,
)
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
    VariableNode,
)


class TestDataModelBuilder:
    def setup_method(self) -> None:
        _register_yaml_constructors()

    @pytest.mark.parametrize(
        "yaml_content,expected_type,expected_value",
        [
            # NumericalVariableNode tests
            pytest.param(
                """
                !!NumericalVariableNode
                name: "var"
                measure_unit: "LengthUnits.Meter"
                initial_value: 10
                """,
                NumericalVariableNode,
                10,
                id="numerical-initial_value_only",
            ),
            pytest.param(
                """
                !!NumericalVariableNode
                name: "var"
                measure_unit: "LengthUnits.Meter"
                default_value: 42
                """,
                NumericalVariableNode,
                42,
                id="numerical-default_value_only",
            ),
            pytest.param(
                """
                !!NumericalVariableNode
                name: "var"
                measure_unit: "LengthUnits.Meter"
                initial_value: 100
                default_value: 50
                """,
                NumericalVariableNode,
                100,
                id="numerical-initial_value_takes_precedence",
            ),
            # StringVariableNode tests
            pytest.param(
                """
                !!StringVariableNode
                name: "str_var"
                initial_value: "hello"
                """,
                StringVariableNode,
                "hello",
                id="string-initial_value_only",
            ),
            pytest.param(
                """
                !!StringVariableNode
                name: "str_var"
                default_value: "world"
                """,
                StringVariableNode,
                "world",
                id="string-default_value_only",
            ),
            pytest.param(
                """
                !!StringVariableNode
                name: "str_var"
                initial_value: "initial"
                default_value: "default"
                """,
                StringVariableNode,
                "initial",
                id="string-initial_value_takes_precedence",
            ),
            # BooleanVariableNode tests
            pytest.param(
                """
                !!BooleanVariableNode
                name: "bool_var"
                initial_value: true
                """,
                BooleanVariableNode,
                True,
                id="boolean-initial_value_only",
            ),
            pytest.param(
                """
                !!BooleanVariableNode
                name: "bool_var"
                default_value: false
                """,
                BooleanVariableNode,
                False,
                id="boolean-default_value_only",
            ),
            pytest.param(
                """
                !!BooleanVariableNode
                name: "bool_var"
                initial_value: true
                default_value: false
                """,
                BooleanVariableNode,
                True,
                id="boolean-initial_value_takes_precedence",
            ),
        ],
    )
    def test_build_variable_node_value(
        self, yaml_content: str, expected_type: type, expected_value: object
    ) -> None:
        """
        Test variable node build from YAML.

        Verify that initial_value, default_value, and their precedence work
        correctly for NumericalVariableNode, StringVariableNode, and
        BooleanVariableNode.
        """
        variable_node = yaml.safe_load(yaml_content)

        assert isinstance(
            variable_node, expected_type
        ), f"Expected type {expected_type}, got {type(variable_node)}"
        assert isinstance(variable_node, VariableNode)  # mypy workaround
        assert variable_node.value == expected_value

    def test_build_object_variable_node_with_properties(self) -> None:
        """
        Test ObjectVariableNode build from YAML with nested properties.

        Verify that nested variable nodes are correctly constructed within the
        ObjectVariableNode.
        """
        yaml_content = """
            !!ObjectVariableNode
            name: "obj_var"
            properties:
                - !!StringVariableNode
                  name: "str_prop"
                  initial_value: "hello"
                - !!NumericalVariableNode
                  name: "num_prop"
                  measure_unit: "LengthUnits.Meter"
                  initial_value: 42
        """

        variable_node = yaml.safe_load(yaml_content)

        assert isinstance(variable_node, ObjectVariableNode)
        assert "str_prop" in variable_node.value
        assert "num_prop" in variable_node.value
        assert variable_node.value["str_prop"] == "hello"
        assert variable_node.value["num_prop"] == 42

    def test_build_folder_node(self) -> None:
        """
        Test FolderNode build from YAML with nested children.
        """
        yaml_content = """
            !!FolderNode
            name: "root_folder"
            description: "Root folder description"
            children:
                - !!StringVariableNode
                  name: "child_var"
                  initial_value: "test"
                - !!FolderNode
                  name: "nested_folder"
                  children: []
        """

        folder_node = yaml.safe_load(yaml_content)

        assert isinstance(folder_node, FolderNode)
        assert folder_node.name == "root_folder"
        assert folder_node.description == "Root folder description"
        assert "child_var" in folder_node.children
        assert "nested_folder" in folder_node.children
        assert isinstance(folder_node.children["child_var"], StringVariableNode)
        assert isinstance(folder_node.children["nested_folder"], FolderNode)

    @pytest.mark.parametrize(
        "yaml_content,expected_type",
        [
            pytest.param(
                """
                !!MethodNode
                name: "test_method"
                description: "A test method"
                parameters:
                    - !!NumericalVariableNode
                      name: "param1"
                      measure_unit: "LengthUnits.Meter"
                      default_value: 15
                returns:
                    - !!BooleanVariableNode
                      name: "success"
                """,
                MethodNode,
                id="sync_method",
            ),
            pytest.param(
                """
                !!AsyncMethodNode
                name: "test_method"
                description: "A test method"
                parameters:
                    - !!NumericalVariableNode
                      name: "param1"
                      measure_unit: "LengthUnits.Meter"
                      default_value: 15
                returns:
                    - !!BooleanVariableNode
                      name: "success"
                """,
                AsyncMethodNode,
                id="async_method",
            ),
        ],
    )
    def test_build_method_node(
        self, yaml_content: str, expected_type: type
    ) -> None:
        """
        Test MethodNode and AsyncMethodNode build from YAML.
        """
        method_node = yaml.safe_load(yaml_content)

        assert isinstance(method_node, expected_type)
        assert isinstance(method_node, MethodNode)  # mypy workaround
        assert method_node.name == "test_method"
        assert method_node.description == "A test method"
        assert len(method_node.parameters) == 1
        assert isinstance(method_node.parameters[0], NumericalVariableNode)
        assert method_node.parameters[0].name == "param1"
        assert method_node.parameters[0].value == 15
        assert len(method_node.returns) == 1

    def test_build_composite_method_node(self) -> None:
        """
        Test CompositeMethodNode build from YAML with control flow.
        """
        yaml_content = """
            !!CompositeMethodNode
            name: "composite_method"
            description: "A composite method"
            parameters: []
            returns: []
            cfg:
                - !!ReadVariableNode
                  variable: "some_var"
                  store_as: "local_var"
        """

        method_node = yaml.safe_load(yaml_content)

        assert isinstance(method_node, CompositeMethodNode)
        assert method_node.name == "composite_method"
        assert isinstance(method_node.cfg, ControlFlow)
        assert len(method_node.cfg.nodes()) == 1

    def test_build_read_variable_node(self) -> None:
        """
        Test ReadVariableNode build from YAML.
        """
        yaml_content = """
            !!ReadVariableNode
            variable: "source_var"
            store_as: "target_var"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, ReadVariableNode)
        assert node.node == "source_var"
        assert node.store_as == "target_var"

    def test_build_write_variable_node(self) -> None:
        """
        Test WriteVariableNode build from YAML.
        """
        yaml_content = """
            !!WriteVariableNode
            variable: "target_var"
            value: "new_value"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, WriteVariableNode)
        assert node.node == "target_var"
        assert node.value == "new_value"

    @pytest.mark.parametrize(
        "expected_operator",
        [
            WaitConditionOperator.EQ,
            WaitConditionOperator.NE,
            WaitConditionOperator.LT,
            WaitConditionOperator.LE,
            WaitConditionOperator.GT,
            WaitConditionOperator.GE,
        ],
    )
    def test_build_wait_condition_node(
        self, expected_operator: WaitConditionOperator
    ) -> None:
        """
        Test WaitConditionNode build from YAML.

        Verify that different operators are correctly parsed.
        Args:
            expected_operator(WaitConditionOperator): The expected operator enum
            value.
        """
        yaml_content = f"""
            !!WaitConditionNode
            variable: "status_var"
            operator: "{expected_operator.value}"
            rhs: "ready"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, WaitConditionNode)
        assert node.node == "status_var"
        assert node.rhs == "ready"
        assert node.op == expected_operator

    def test_build_call_method_node(self) -> None:
        """
        Test CallMethodNode build from YAML.
        """
        yaml_content = """
            !!CallMethodNode
            method: "target_method"
            args:
                - "arg1"
                - 42
            kwargs:
                key1: "value1"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, CallMethodNode)
        assert node.node == "target_method"
        assert node.args == ["arg1", 42]
        assert node.kwargs == {"key1": "value1"}

    def test_build_call_remote_method_node(self) -> None:
        """
        Test CallRemoteMethodNode build from YAML.
        """
        yaml_content = """
            !!CallRemoteMethodNode
            method: "remote_method"
            remote_id: "server_1"
            args: [12, "param"]
            kwargs: {"option": true}
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, CallRemoteMethodNode)
        assert node.node == "remote_method"
        assert node.remote_id == "server_1"
        assert node.args == [12, "param"]
        assert node.kwargs == {"option": True}

    def test_build_read_remote_variable_node(self) -> None:
        """
        Test ReadRemoteVariableNode build from YAML.
        """
        yaml_content = """
            !!ReadRemoteVariableNode
            variable: "remote_var"
            remote_id: "server_1"
            store_as: "local_var"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, ReadRemoteVariableNode)
        assert node.node == "remote_var"
        assert node.remote_id == "server_1"
        assert node.store_as == "local_var"

    def test_build_write_remote_variable_node(self) -> None:
        """
        Test WriteRemoteVariableNode build from YAML.
        """
        yaml_content = """
            !!WriteRemoteVariableNode
            variable: "remote_var"
            remote_id: "server_1"
            value: "new_value"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, WriteRemoteVariableNode)
        assert node.node == "remote_var"
        assert node.remote_id == "server_1"
        assert node.value == "new_value"

    @pytest.mark.parametrize(
        "expected_operator",
        [
            WaitConditionOperator.EQ,
            WaitConditionOperator.NE,
            WaitConditionOperator.LT,
            WaitConditionOperator.LE,
            WaitConditionOperator.GT,
            WaitConditionOperator.GE,
        ],
    )
    def test_build_wait_remote_event_node(
        self, expected_operator: WaitConditionOperator
    ) -> None:
        """
        Test WaitRemoteEventNode build from YAML.

        Verify that different operators are correctly parsed.

        Args:
            expected_operator(WaitConditionOperator): The expected operator enum
            value.
        """
        yaml_content = f"""
            !!WaitRemoteEventNode
            variable: "remote_status"
            operator: "{expected_operator.value}"
            rhs: "completed"
            remote_id: "server_1"
        """

        node = yaml.safe_load(yaml_content)

        assert isinstance(node, WaitRemoteEventNode)
        assert node.node == "remote_status"
        assert node.op == expected_operator
        assert node.rhs == "completed"
        assert node.remote_id == "server_1"
