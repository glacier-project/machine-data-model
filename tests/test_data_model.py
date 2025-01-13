import random

import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import NumericalVariableNode, VariableNode
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

        root_node = data_model.get_node_from_path(root.name)
        node = data_model.get_node_from_path(f"{root.name}/{child.name}")

        assert data_model.name == "dm"
        assert root_node == root
        assert node == child

    def test_data_model_search_by_path_not_found(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        with pytest.raises(ValueError):
            data_model.get_node_from_path("not_found")

    def test_data_model_search_by_id(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        root = data_model.root
        child = random.choice(list(root.children.values()))

        root_node = data_model.get_node_from_id(root.id)
        node = data_model.get_node_from_id(child.id)

        assert data_model.name == "dm"
        assert root_node == root
        assert node == child

    def test_data_model_search_by_id_not_found(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        with pytest.raises(ValueError):
            data_model.get_node_from_id("not_found")

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
        child = None
        if list_of_numerical_nodes != []:
            child = random.choice(list_of_numerical_nodes)

            new_value = random.random()
            data_model.write_variable(child.id, new_value)

            assert data_model.read_variable(child.id) == new_value

    def test_call_method(self, root: FolderNode) -> None:
        def callback() -> str:
            return "callback_result"

        method_nodes = [
            node for node in root.children.values() if isinstance(node, MethodNode)
        ]

        if method_nodes != []:
            method = random.choice(method_nodes)
            method.callback = callback
            data_model = DataModel(name="dm", root=root)
            result = data_model.call_method(method.id)
            assert result == "callback_result"

    def test_deserialize_and_serialize_data_model(self, root: FolderNode) -> None:
        data_model = DataModel(name="dm", root=root)

        serialized_data_model = data_model.serialize()
        deserialized_data_model = DataModel.deserialize(serialized_data_model)

        assert deserialized_data_model.name == data_model.name
        assert deserialized_data_model.machine_category == data_model.machine_category
        assert deserialized_data_model.machine_type == data_model.machine_type
        assert deserialized_data_model.machine_model == data_model.machine_model
        assert deserialized_data_model.description == data_model.description
        assert deserialized_data_model.root == data_model.root