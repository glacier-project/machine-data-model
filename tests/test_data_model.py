import random

import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.folder_node import FolderNode
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
