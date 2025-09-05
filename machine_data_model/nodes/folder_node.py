from typing import Iterator

from typing_extensions import override

from machine_data_model.nodes.data_model_node import DataModelNode


class FolderNode(DataModelNode):
    """
    A FolderNode class is a node that represents a folder in the machine data model.
    Folders of the machine data model are used to organize the node of the machine data
    model in a hierarchical structure.

    :ivar _children: A dictionary of child nodes within the folder.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        children: dict[str, DataModelNode] | None = None,
        connector_name: str | None = None,
        remote_path: str | None = None,
    ):
        """
        Initializes a new FolderNode instance.

        :param id: The unique identifier of the folder.
        :param name: The name of the folder.
        :param description: The description of the folder.
        :param children: A dictionary of child nodes of the folder.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            connector_name=connector_name,
            remote_path=remote_path,
        )
        self._children = {} if children is None else children
        for child in self._children.values():
            assert isinstance(child, DataModelNode), "Child must be a DataModelNode"
        self.register_children(self._children)

    @property
    def children(self) -> dict[str, DataModelNode]:
        """
        Returns the child nodes of the folder.

        :return: A dictionary of child nodes, where keys are node names and values are `DataModelNode` instances.
        """
        return self._children

    def add_child(self, child: DataModelNode) -> None:
        """
        Add a child node to the folder.

        :param child: The child node to add to the folder.
        """
        assert isinstance(child, DataModelNode), "Child must be a DataModelNode"
        self._children[child.name] = child
        child.parent = self

    def remove_child(self, child_name: str) -> None:
        """
        Remove a child node from the folder.

        :param child_name: The name of the child node to remove from the folder.
        """
        if child_name in self._children:
            child = self._children[child_name]
            del self._children[child_name]
            child.parent = None
        else:
            raise ValueError(
                f"Child node with name '{child_name}' not found in folder '{self.name}'"
            )

    def has_child(self, child_name: str) -> bool:
        """
        Check if the folder has a child node with the specified name.

        :param child_name: The name of the child node to check.
        :return: True if the folder has a child node with the specified name, False otherwise.
        """
        return child_name in self._children

    @override
    def __getitem__(self, child_name: str) -> DataModelNode:
        """
        Get a child node from the folder by name.

        :param child_name: The name of the child node to get from the folder.
        :return: The child node with the specified name.
        """
        return self._children[child_name]

    @override
    def __contains__(self, child_name: str) -> bool:
        """
        Check if the folder has a child node with the specified name.

        :param child_name: The name of the child node to check.
        :return: True if the folder has a child node with the specified name, False otherwise.
        """
        return self.has_child(child_name)

    @override
    def __iter__(self) -> Iterator[DataModelNode]:
        """
        Iterate over the children of the folder.

        :return: An iterator over the children of the folder.
        """
        children = self._children
        for child in children:
            yield children[child]

    def __str__(self) -> str:
        """
        Returns a string representation of the FolderNode.

        :return: A string describing the FolderNode.
        """
        return (
            f"FolderNode(id={self._id}, name={self._name}, "
            f"description={self._description}, children={self._children}, connector_name={repr(self.connector_name)}, "
            f"remote_path={repr(self.remote_path)})"
        )

    def __repr__(self) -> str:
        """
        Returns a string representation of the FolderNode.

        :return: The string representation of the FolderNode (same as `__str__`).
        """
        return self.__str__()
