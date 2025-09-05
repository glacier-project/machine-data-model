import uuid
from abc import ABC, abstractmethod
from typing import Iterator, Mapping, Sequence, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from machine_data_model.nodes.connectors.abstract_connector import AbstractConnector
else:
    AbstractConnector = Any


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
        connector_name: str | None = None,
        remote_path: str | None = None,
    ):
        """
        Initializes a new `DataModelNode` instance.

        :param id: The unique identifier of the node. If `None`, a new UUID is generated.
        :param name: The name of the node. If `None`, the name is set to an empty string.
        :param description: A description of the node. If `None`, the description is set to an empty string.
        :param connector_name: The name of the connector to use to interact with the server.
                               If it is `None`, and the hierarchy of the node also doesn't define this attribute,
                               the node is not a remote node: interacting with the node will change the internal value.
        :param remote_path: The remote path of the node in the server.
                            Allows to override the qualified name of the node, defined by the yaml config structure.
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

        # -- connector management
        self._connector_name: str | None = connector_name
        self._connector: AbstractConnector | None = None
        self._remote_path: str | None = remote_path

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

    def set_name(self, value: str) -> None:
        """Sets the name of the node."""
        self._name = value

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

    def set_description(self, value: str) -> None:
        """Sets the description of the node."""
        self._description = value

    @property
    def connector_name(self) -> str | None:
        return self._connector_name

    def set_connector_name(self, value: str | None) -> None:
        """Sets the connector name."""
        self._connector_name = value

    def is_remote(self) -> bool:
        """
        Returns True if the current node is a remote node,
        which means that to interact with it, we need to use its connector.
        A node is a remote node if the user defined the 'connector_name' attribute in the yaml file.

        :return: True if the current node is a remote node, False otherwise.
        """
        return self.connector_name is not None

    def is_connector_set(self) -> bool:
        """
        Returns True if the connector was set.
        A remote node (is_remote() == True) must have, at some point, its connector set up.

        :return: True if the connector is set, False otherwise.
        """
        return self._connector is not None

    def set_connector(self, connector: AbstractConnector | None) -> None:
        """
        Sets the connector which will be used to interact with this variable.

        :param connector: The node's connector.
        """
        self._connector = connector

    @property
    def connector(self) -> AbstractConnector | None:
        """Connector getter."""
        return self._connector

    def is_remote_path_set(self) -> bool:
        """
        Returns True if the remote path is set.
        The remote path is the path used by the connector to interact with the remote variable.

        :return: True if the remote path is set.
        """
        return self._remote_path is not None

    def set_remote_path(self, remote_path: str | None) -> None:
        """
        Sets the remote path, which is used to interact with the remote variable.
        """
        self._remote_path = remote_path

    @property
    def remote_path(self) -> str | None:
        """Remote path getter."""
        return self._remote_path

    def register_children(
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

    def __eq__(self, other: object) -> bool:
        """
        Check if two nodes are equal based on their IDs.

        :param other: The other node to compare with.
        :return: True if the nodes are equal, False otherwise.
        """
        if not isinstance(other, DataModelNode):
            return False
        return (
            self.id == other.id
            and self.name == other.name
            and self.description == other.description
        )
