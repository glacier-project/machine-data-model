import random

import pytest

from typing import Any

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    VariableNode,
    StringVariableNode,
)
from machine_data_model.nodes.method_node import MethodNode
from tests import get_random_folder_node


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
        def callback() -> str:
            return "result"

        method = MethodNode(
            name="method",
            callback=callback,
            returns=[StringVariableNode(name="return_value", value="")],
        )
        root.add_child(method)
        data_model = DataModel(name="dm", root=root)
        result = data_model.call_method(method.id)
        assert result["return_value"] == "result"

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
        child.update("Perfect!")
        # Assert that the child node has subscribers.
        assert child.has_subscribers()
        # Assert that the changes list contains the expected value.
        assert ("A", child, "Perfect!") in changes
        assert ("B", child, "Perfect!") in changes
