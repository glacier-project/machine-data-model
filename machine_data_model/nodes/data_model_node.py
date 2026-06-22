"""Data model node base classes.

This module provides the abstract base class for all nodes in the machine data
model, defining common attributes and methods that all node types share.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING
import uuid
import weakref

from .connectors.abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)
from .connectors.remote_resource import RemoteResource

if TYPE_CHECKING:
    from machine_data_model.data_model import DataModel
    from machine_data_model.nodes.connectors.abstract_connector import (
        AbstractConnector,
    )


class DataModelNode(ABC):
    """Abstract base class representing a node in the machine data model.

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
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ):
        """Initializes a new `DataModelNode` instance.

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
            connector_name (str | None):
                The name of the connector to use to interact with the server.
                If it is `None`, and the hierarchy of the node also doesn't
                define this attribute, the node is not a remote node:
                interacting with the node will change the internal value.
            remote_resource_spec (RemoteResourceSpec | None):
                Protocol-specific properties for the remote resource.

        """
        self._id: str = str(uuid.uuid4()) if id is None else id
        if not (isinstance(self._id, str) and len(self._id) > 0):
            raise RuntimeError("ID must be a non-empty string")
        self._name: str = "" if name is None else name
        if not isinstance(self._name, str):
            raise TypeError("Name must be a string")
        self._description = "" if description is None else description
        if not isinstance(self._description, str):
            raise TypeError("Description must be a string")
        self.parent: DataModelNode | None = None
        self._data_model: weakref.ReferenceType[DataModel] | None = None

        # -- connector management
        self._connector_name: str | None = connector_name
        self._connector: AbstractConnector | None = None
        self._remote_path: str | None = None
        self._remote_resource_spec: AbstractRemoteResourceSpec | None = (
            remote_resource_spec
        )
        self._remote_resource: RemoteResource | None = None

    @property
    def id(self) -> str:
        """Gets the unique identifier of the node.

        Returns:
            str:
                The unique identifier of the node.

        """
        return self._id

    @property
    def qualified_name(self) -> str:
        """Gets the qualified name of the node.

        Returns:
            str:
                The qualified name of the node.

        """
        p_qualified_name = self.parent.qualified_name if self.parent else ""
        return f"{p_qualified_name}/{self.name}"

    @property
    def name(self) -> str:
        """Gets the name of the node.

        Returns:
            str:
                The name of the node.

        """
        return self._name

    def set_name(self, value: str) -> None:
        """Sets the name of the node."""
        self._name = value

    @property
    def description(self) -> str:
        """Gets the description of the node.

        Returns:
            str:
                The description of the node.

        """
        return self._description

    def set_description(self, value: str) -> None:
        """Sets the description of the node."""
        self._description = value

    @property
    def connector_name(self) -> str | None:
        """Gets the connector name.

        Returns:
            str | None:
                The connector name, or None if not set.
        """
        return self._connector_name

    @property
    def remote_resource_spec(self) -> AbstractRemoteResourceSpec | None:
        """Gets the remote resource spec.

        Returns:
            AbstractRemoteResourceSpec | None:
                The remote resource spec, or None if not set.
        """
        return self._remote_resource_spec

    @remote_resource_spec.setter
    def remote_resource_spec(
        self, value: AbstractRemoteResourceSpec | None
    ) -> None:
        """Sets the remote resource spec.

        Args:
            value (AbstractRemoteResourceSpec | None):
                The remote resource spec to set.
        """
        self._remote_resource_spec = value
        self._remote_resource = None

    def set_connector_name(self, value: str | None) -> None:
        """Sets the connector name."""
        self._connector_name = value

    def is_remote(self) -> bool:
        """Returns True if the current node is a remote node.

        Remote nodes are nodes that represent remote resources, i.e., resources
        that are not stored locally but are accessed via a connector.

        Returns:
            bool:
                True if the current node is a remote node, False otherwise.
        """
        return self.connector_name is not None

    def has_connector(self) -> bool:
        """Returns True if the connector was set.

        A remote node (is_remote() == True) must have, at some point, its
        connector set up.

        Returns:
            bool:
                True if the connector is set, False otherwise.
        """
        return self._connector is not None

    def set_connector(self, connector: "AbstractConnector | None") -> None:
        """Sets the connector which will be used to interact with this variable.

        Args:
            connector (AbstractConnector | None):
                The node's connector.
        """
        self._connector = connector

    @property
    def connector(self) -> "AbstractConnector | None":
        """Connector getter."""
        return self._connector

    def has_remote_path(self) -> bool:
        """Returns True if the remote path is set.

        The remote path is the path used by the connector to interact with the
        remote variable.

        Returns:
            bool:
                True if the remote path is set.
        """
        return self._remote_path is not None

    def set_remote_path(self, remote_path: str | None) -> None:
        """Sets the remote path used by the connector."""
        self._remote_path = remote_path
        self._remote_resource = None

    @property
    def remote_path(self) -> str | None:
        """Returns the remote path.

        If the node doesn't have a remote path,
        it tries to use the remote resource specs to retrieve it.
        """
        if self._remote_path is not None:
            return self._remote_path

        if self._remote_resource_spec is not None:
            return self._remote_resource_spec.get_remote_path(self)

        return None

    @property
    def remote_resource(self) -> RemoteResource:
        """Return the resolved remote resource for this node.

        DataModel setup configures this once after inherited specs, remote path,
        and connector inheritance have been resolved. The lazy fallback keeps
        manually wired nodes usable in tests and direct integrations.
        """
        if self._remote_resource is None:
            return self.configure_remote_resource()
        return self._remote_resource

    def configure_remote_resource(self) -> RemoteResource:
        """Resolve and store the connector-facing remote resource."""
        self._remote_resource = RemoteResource.from_node(self)
        return self._remote_resource

    @property
    def data_model(self) -> "DataModel | None":
        """Gets the data model that contains this node.

        Returns:
            DataModel | None:
                he data model containing this node, or None if not set.

        """
        return self._data_model() if self._data_model is not None else None

    def set_data_model(self, data_model: "DataModel") -> None:
        """Sets the data model that contains this node.

        Args:
            data_model (DataModel):
                The data model to set.

        """
        self._data_model = weakref.ref(data_model)

    def register_children(
        self,
        child_nodes: Mapping[str, "DataModelNode"] | Sequence["DataModelNode"],
    ) -> None:
        """Set this node as the parent of the child nodes.

        Args:
            child_nodes:
                The child nodes to set the parent for.

        """
        if isinstance(child_nodes, dict):
            child_nodes = list(child_nodes.values())

        if not isinstance(child_nodes, list):
            raise TypeError("Expected child_nodes to be an instance of list")
        for child in child_nodes:
            child.parent = self

    @abstractmethod
    def __getitem__(self, child_name: str) -> "DataModelNode":
        """Get a child node by name.

        Args:
            child_name (str):
                The name of the child node.

        Returns:
            DataModelNode:
                The child node with the specified name.

        """

    @abstractmethod
    def __contains__(self, child_name: str) -> bool:
        """Check if the node contains a child with the specified name.

        Args:
            child_name (str):
                The name of the child node.

        Returns:
            bool:
                True if the child exists, False otherwise.

        """

    @abstractmethod
    def __iter__(self) -> Iterator["DataModelNode"]:
        """Iterate over the children of the node.

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
