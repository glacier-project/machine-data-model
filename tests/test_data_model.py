import random

import pytest
import os
from typing import Any
from machine_data_model.data_model import DataModel
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    VariableNode,
    StringVariableNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from tests import get_random_folder_node


def get_template_data_model() -> DataModel:
    # Construct the absolute path from the data_model.yml file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "../template/data_model.yml")

    # Use DataModelBuilder to load the data model
    builder = DataModelBuilder()
    data_model = builder.get_data_model(file_path)

    return data_model


@pytest.mark.parametrize("root", [get_random_folder_node() for _ in range(3)])
class TestDataModel:
    def test_simple_data_model(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        assert data_model.name == "dm"
        assert data_model.root == root

    def test_data_model_search_by_path(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        root = data_model.root
        child = random.choice(list(root.children.values()))

        root_node = data_model.get_node(f"/{root.name}")
        node = data_model.get_node(f"{root.name}/{child.name}")

        assert data_model.name == "dm"
        assert root_node == root
        assert node == child

    def test_data_model_search_by_path_not_found(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        node = data_model.get_node("not_found")
        assert node is None

    def test_data_model_search_by_id(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        root = data_model.root
        child = random.choice(list(root.children.values()))

        root_node = data_model.get_node(root.id)
        node = data_model.get_node(child.id)

        assert data_model.name == "dm"
        assert root_node == root
        assert node == child

    def test_data_model_search_by_id_not_found(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        node = data_model.get_node("not_found")
        assert node is None

    def test_read_variable(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        root = data_model.root
        child = random.choice(
            [
                node
                for node in root.children.values()
                if not isinstance(node, MethodNode)
            ]
        )
        value = data_model.read_variable(child.id)
        if isinstance(child, VariableNode):
            assert value == child.read()

    def test_write_variable(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        root = data_model.root
        list_of_numerical_nodes = [
            node
            for node in root.children.values()
            if isinstance(node, NumericalVariableNode)
        ]

        child = random.choice(list_of_numerical_nodes)

        new_value = random.random()
        data_model.write_variable(child.id, new_value)

        assert data_model.read_variable(child.id) == new_value

    def test_call_method(self, root: FolderNode) -> None:
        def callback(input: str) -> str:
            return input

        method = MethodNode(
            name="method",
            callback=callback,
            parameters=[StringVariableNode(name="input", value="Test")],
            returns=[StringVariableNode(name="return_value", value="")],
        )
        root.add_child(method)
        data_model = DataModel(name="dm", root=root)
        result = data_model.call_method(method.id)
        assert result.return_values["return_value"] == "Test"

    def test_subscribe(self, root: FolderNode) -> None:
        # Tracks the list of changes.
        changes = []

        # Setup callback to handle subscriber notifications.
        def update_message_callback(
            subscriber: str, node: VariableNode, value: Any
        ) -> None:
            # For this test, we'll append the notification data to 'changes' (or
            # any tracking list).
            changes.append((subscriber, node, value))

        # Create the data model and set up the root node.
        data_model = DataModel(name="dm", root=root)
        root = data_model.root
        # Randomly select a child node of type StringVariableNode from the root.
        child = random.choice(
            [
                node
                for node in root.children.values()
                if isinstance(node, StringVariableNode)
            ]
        )
        # Subscribe a "A" subscriber to the child node.
        data_model.subscribe(child.id, "A")
        # Subscribe a "B" subscriber to the child node.
        data_model.subscribe(child.id, "B")
        # Set the subscription callback (callback will handle the actual message
        # creation and storage).
        child.set_subscription_callback(update_message_callback)
        # Perform an update on the child node, triggering the deferred notify
        # mechanism.
        child.write("Perfect!")
        # Assert that the child node has subscribers.
        assert child.has_subscribers()
        # Assert that the changes list contains the expected value.
        assert ("A", child, "Perfect!") in changes
        assert ("B", child, "Perfect!") in changes

    def test_runtime_resolution_of_nodes(self, root: FolderNode) -> None:
        data_model = get_template_data_model()
        # scope = ControlFlowScope(str("test"))
        assert isinstance(data_model, DataModel)
        r = data_model.get_node("folder1/folder2")
        assert isinstance(r, FolderNode)
        composite_node = r["comp_test"]
        assert isinstance(composite_node, CompositeMethodNode)
        args: list[Any] = [True, "folder1/boolean"]
        assert isinstance(composite_node, CompositeMethodNode)
        ret = composite_node(*args)

        assert not ret.messages
        assert ret.return_values["@scope_id"]

        data_model.write_variable("folder1/boolean", True)
        ret = composite_node(*args)

        assert ret.return_values["var_out"]


class TestDataModelTracing:
    def test_tracing_disabled_by_default(self) -> None:
        data_model = DataModel()
        assert not data_model._enable_tracing
        assert data_model._trace_log == []

    def test_tracing_enabled(self) -> None:
        data_model = DataModel(enable_tracing=True)
        assert data_model._enable_tracing

    def test_tracing_records_changes(self) -> None:
        data_model = DataModel(enable_tracing=True)
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        data_model.write_variable("test_var", 20.0)

        assert len(data_model._trace_log) == 1
        entry = data_model._trace_log[0]
        assert entry.variable_id == "test_var"
        assert entry.old_value == 10.0
        assert entry.new_value == 20.0
        assert isinstance(entry.timestamp, float)

    def test_export_trace(self, tmp_path) -> None:
        data_model = DataModel(enable_tracing=True)
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        data_model.write_variable("test_var", 20.0)

        filepath = tmp_path / "trace.csv"
        data_model.export_trace(str(filepath))

        with open(filepath) as f:
            lines = f.readlines()

        assert lines[0].strip() == "timestamp,variable_id,old_value,new_value"
        assert len(lines) == 2
        parts = lines[1].strip().split(",")
        assert parts[1] == "test_var"
        assert parts[2] == "10.0"
        assert parts[3] == "20.0"
