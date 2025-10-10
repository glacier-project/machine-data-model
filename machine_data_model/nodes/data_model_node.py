"""
Data model node base classes.

This module provides the abstract base class for all nodes in the machine data model,
defining common attributes and methods that all node types share.
"""

import uuid
import weakref
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from machine_data_model.data_model import DataModel


class DataModelNode(ABC):
    """
    Abstract base class representing a node in the machine data model.

    This class defines common attributes for nodes within the machine data
    model, including a unique identifier, a name, and a description. Subclasses
    should extend this to represent more specific types of nodes in the model.

    Attributes:
        _id (str):
            The unique identifier of the node.
        _name (str):
            The name of the node.
        _description (str):
            A description of the node.
        parent (DataModelNode | None):
            A reference to the parent node in the data model hierarchy, or None
            if the node is a root node.
        _data_model (weakref.ReferenceType[DataModel] | None):
            A weak reference to the DataModel instance that contains this node,
            or None if the node is not yet associated with a data model.

    """

    _id: str
    _name: str
    _description: str
    parent: "DataModelNode | None"
    _data_model: weakref.ReferenceType["DataModel"] | None

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        """
        Initializes a new `DataModelNode` instance.

        Args:
            id (str | None):
                The unique identifier of the node. If `None`, a new UUID is
                generated.
            name (str | None):
                The name of the node. If `None`, the name is set to an empty
                string.
            description (str | None):
                A description of the node. If `None`, the description is set to
                an empty string.

        """
        self._id: str = str(uuid.uuid4()) if id is None else id
        assert (
            isinstance(self._id, str) and len(self._id) > 0
        ), "ID must be a non-empty string"
        self._name: str = "" if name is None else name
        assert isinstance(self._name, str), "Name must be a string"
        self._description = "" if description is None else description
        assert isinstance(self._description, str), "Description must be a string"
        self.parent: DataModelNode | None = None
        self._data_model: weakref.ReferenceType[DataModel] | None = None

    @property
    def id(self) -> str:
        """
        Gets the unique identifier of the node.

        Returns:
            str:
                The unique identifier of the node.

        """
        return self._id

    @property
    def qualified_name(self) -> str:
        """
        Gets the qualified name of the node.

        Returns:
            str:
                The qualified name of the node.

        """
        p_qualified_name = self.parent.qualified_name if self.parent else ""
        return f"{p_qualified_name}/{self.name}"

    @property
    def name(self) -> str:
        """
        Gets the name of the node.

        Returns:
            str:
                The name of the node.

        """
        return self._name

    ## Git commit
    # Introduce composite method nodes to the machine data model. Composite method nodes
    # are used to implement the logic of a run-time method in the machine data model.

    @property
    def description(self) -> str:
        """
        Gets the description of the node.

        Returns:
            str:
                The description of the node.

        """
        return self._description

    @property
    def data_model(self) -> "DataModel | None":
        """
        Gets the data model that contains this node.

        Returns:
            DataModel | None:
                he data model containing this node, or None if not set.

        """
        return self._data_model() if self._data_model is not None else None

    def register_children(
        self, child_nodes: Mapping[str, "DataModelNode"] | Sequence["DataModelNode"]
    ) -> None:
        """
        Set this node as the parent of the child nodes.

        Args:
            child_nodes (Mapping[str, "DataModelNode"] |
            Sequence["DataModelNode"]):
                The child nodes to set the parent for.

        """
        if isinstance(child_nodes, dict):
            child_nodes = list(child_nodes.values())

        assert isinstance(child_nodes, list)
        for child in child_nodes:
            child.parent = self

    @abstractmethod
    def __getitem__(self, child_name: str) -> "DataModelNode":
        """
        Get a child node by name.

        Args:
            child_name (str):
                The name of the child node.

        Returns:
            DataModelNode:
                The child node with the specified name.

        """

    @abstractmethod
    def __contains__(self, child_name: str) -> bool:
        """
        Check if the node contains a child with the specified name.

        Args:
            child_name (str):
                The name of the child node.

        Returns:
            bool:
                True if the child exists, False otherwise.

        """

    @abstractmethod
    def __iter__(self) -> Iterator["DataModelNode"]:
        """
        Iterate over the children of the node.

        Returns:
            Iterator[DataModelNode]:
                An iterator over the children of the node.

        """

    def _eq_base(self, other: "DataModelNode") -> bool:
        return (
            self.id == other.id
            and self.name == other.name
            and self.description == other.description
        )
