"""
Folder node implementation for machine data models.

This module provides the FolderNode class, which represents folders in the
machine data model hierarchy used to organize nodes in a tree structure.
"""

from collections.abc import Iterator

from typing_extensions import override

from machine_data_model.nodes.data_model_node import DataModelNode


class FolderNode(DataModelNode):
    """
    A FolderNode class is a node that represents a folder in the machine data
    model. Folders of the machine data model are used to organize the node of
    the machine data model in a hierarchical structure.

    Attributes:
        _children:
            A dictionary of child nodes within the folder.

    """

    _children: dict[str, DataModelNode]

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        children: dict[str, DataModelNode] | None = None,
    ):
        """
        Initializes a new FolderNode instance.

        Args:
            id (str | None):
                The unique identifier of the folder.
            name (str | None):
                The name of the folder.
            description (str | None):
                The description of the folder.
            children (dict[str, DataModelNode] | None):
                A dictionary of child nodes of the folder.

        """
        super().__init__(id=id, name=name, description=description)
        self._children = {} if children is None else children
        for child in self._children.values():
            assert isinstance(child, DataModelNode), "Child must be a DataModelNode"
        self.register_children(self._children)

    @property
    def children(self) -> dict[str, DataModelNode]:
        """
        Returns the child nodes of the folder.

        Returns:
            dict[str, DataModelNode]:
                A dictionary of child nodes, where keys are node names and
                values are `DataModelNode` instances.

        """
        return self._children

    def add_child(self, child: DataModelNode) -> None:
        """
        Add a child node to the folder.

        Args:
            child (DataModelNode):
                The child node to add to the folder.

        """
        assert isinstance(child, DataModelNode), "Child must be a DataModelNode"
        self._children[child.name] = child
        child.parent = self

    def remove_child(self, child_name: str) -> None:
        """
        Remove a child node from the folder.

        Args:
            child_name (str):
                The name of the child node to remove from the folder.

        Raises:
            ValueError:
                If the child node with the specified name is not found.

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

        Args:
            child_name (str):
                The name of the child node to check.

        Returns:
            bool:
                True if the folder has a child node with the specified name,
                False otherwise.

        """
        return child_name in self._children

    @override
    def __getitem__(self, child_name: str) -> DataModelNode:
        """
        Get a child node from the folder by name.

        Args:
            child_name (str):
                The name of the child node to get from the folder.

        Returns:
            DataModelNode:
                The child node with the specified name.

        """
        return self._children[child_name]

    @override
    def __contains__(self, child_name: str) -> bool:
        """
        Check if the folder has a child node with the specified name.

        Args:
            child_name (str):
                The name of the child node to check.

        Returns:
            bool:
                True if the folder has a child node with the specified name,
                False otherwise.

        """
        return self.has_child(child_name)

    @override
    def __iter__(self) -> Iterator[DataModelNode]:
        """
        Iterate over the children of the folder.

        Returns:
            Iterator[DataModelNode]:
                An iterator over the children of the folder.

        """
        children = self._children
        for child in children:
            yield children[child]

    def __str__(self) -> str:
        """
        Returns a string representation of the FolderNode.

        Returns:
            str:
                A string describing the FolderNode.

        """
        return (
            f"FolderNode(id={self._id}, name={self._name}, "
            f"description={self._description}, children={self._children})"
        )

    def __repr__(self) -> str:
        """
        Returns a string representation of the FolderNode.

        Returns:
            str:
                The string representation of the FolderNode (same as `__str__`).

        """
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, FolderNode):
            return False

        if not self._eq_base(other):
            return False

        return self._children == other._children
