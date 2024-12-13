import pytest

from machine_data_model.nodes.folder_node import FolderNode
from tests import NUM_TESTS, gen_random_string, get_random_simple_node


@pytest.mark.parametrize(
    "folder_name, folder_description",
    [(gen_random_string(10), gen_random_string(20)) for _ in range(3)],
)
class TestFolderNode:

    @pytest.mark.parametrize(
        "children",
        [
            [get_random_simple_node() for _ in range(NUM_TESTS)]
            for _ in range(NUM_TESTS)
        ],
    )
    def test_folder_node_creation(self, folder_name, folder_description, children):
        folder = FolderNode(name=folder_name, description=folder_description)

        for child in children:
            folder.add_child(child)

        assert folder.name == folder_name
        assert folder.description == folder_description
        assert len(folder.children) == len(children)
        for child in children:
            assert folder.has_child(child.name)
            assert folder[child.name] == child

    @pytest.mark.parametrize(
        "children",
        [
            [get_random_simple_node() for _ in range(NUM_TESTS)]
            for _ in range(NUM_TESTS)
        ],
    )
    def test_folder_node_update(self, folder_name, folder_description, children):
        folder = FolderNode(name=folder_name, description=folder_description)

        for child in children:
            folder.add_child(child)

        to_remove = children[0]
        folder.remove_child(children[0].name)
        del children[0]
        new_child = get_random_simple_node()
        folder.add_child(new_child)

        assert folder.name == folder_name
        assert folder.description == folder_description
        assert len(folder.children) == len(children) + 1
        for child in children:
            assert folder.has_child(child.name)
            assert folder[child.name] == child
        assert not folder.has_child(to_remove.name)
        assert folder.has_child(new_child.name)
