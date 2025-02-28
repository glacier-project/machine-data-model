import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Mapping, Sequence


class DataModelNode(ABC):
    """
    Abstract base class representing a node in the machine data model.

    This class defines common attributes for nodes within the machine data
    model, including a unique identifier, a name, and a description. Subclasses
    should extend this to represent more specific types of nodes in the model.

    :ivar _id: The unique identifier of the node.
    :ivar _name: The name of the node.
    :ivar _description: A description of the node.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        """
        Initializes a new `DataModelNode` instance.

        :param id: The unique identifier of the node. If `None`, a new UUID is generated.
        :param name: The name of the node. If `None`, the name is set to an empty string.
        :param description: A description of the node. If `None`, the description is set to an empty string.
        """

        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name: str = "" if name is None else name
        self._description = "" if description is None else description
        self.parent: DataModelNode | None = None

    @property
    def id(self) -> str:
        """
        Gets the unique identifier of the node.

        :return: The unique identifier of the node.
        """
        return self._id

    @property
    def qualified_name(self) -> str:
        """
        Gets the qualified name of the node.

        :return: The qualified name of the node.
        """
        p_qualified_name = self.parent.qualified_name if self.parent else ""
        return f"{p_qualified_name}/{self.name}"

    @property
    def name(self) -> str:
        """
        Gets the name of the node.

        :return: The name of the node.
        """
        return self._name

    ## Git commit
    # Introduce composite method nodes to the machine data model. Composite method nodes
    # are used to implement the logic of a run-time method in the machine data model.

    @property
    def description(self) -> str:
        """
        Gets the description of the node.

        :return: The description of the node.
        """
        return self._description

    def set_parent(
        self, child_nodes: Mapping[str, "DataModelNode"] | Sequence["DataModelNode"]
    ) -> None:
        """
        Set this node as the parent of the child nodes.

        :param child_nodes: The child nodes to set the parent for.
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

        :param child_name: The name of the child node.
        :return: The child node with the specified name.
        """
        pass

    @abstractmethod
    def __contains__(self, child_name: str) -> bool:
        """
        Check if the node contains a child with the specified name.

        :param child_name: The name of the child node.
        :return: True if the child exists, False otherwise.
        """
        pass

    @abstractmethod
    def __iter__(self) -> Iterator["DataModelNode"]:
        """
        Iterate over the children of the node.

        :return: An iterator over the children of the node.
        """
        pass
