from typing import TYPE_CHECKING, Any

import asyncua
from asyncua import Node
from typing_extensions import override

from machine_data_model.nodes.connectors.abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)

if TYPE_CHECKING:
    from machine_data_model.nodes.data_model_node import DataModelNode


class OpcuaRemoteResourceSpec(AbstractRemoteResourceSpec):
    """Represents node properties that are specific for the OPC UA protocol."""

    def __init__(
        self,
        remote_path: str | None = None,
        node_id: str | None = None,
        namespace: str | None = None,
        parent_node_id: str | None = None,
    ) -> None:
        """Constructor.

        Args:
            remote_path (str, optional):
                Node's path on the remote OPC UA server.
            node_id (str, optional):
                Node's id on the remote OPC UA server.
            namespace (str, optional):
                Node's namespace on the remote OPC UA server.
            parent_node_id (str, optional):
                Parent node's id of node_id on the remote OPC UA server.
        """
        super().__init__(remote_path=remote_path)
        self.node_id: str | None = node_id
        self.parent_node_id: str | None = parent_node_id
        self.namespace: str | None = namespace
        self.remote_node: Node | None = None

    def has_node_id(self) -> bool:
        """Returns whether this spec has a node id defined.

        Returns:
            bool:
                True if a node id is defined, False otherwise.
        """
        return self.node_id is not None and self.node_id != ""

    def has_parent_node_id(self) -> bool:
        """Returns whether this spec has a parent node id defined.

        Returns:
            bool:
                True if a parent node id is defined, False otherwise.
        """
        return self.parent_node_id is not None and self.parent_node_id != ""

    def has_namespace(self) -> bool:
        """Returns whether this spec has a namespace defined.

        Returns:
            bool:
                True if a namespace is defined, False otherwise.
        """
        return self.namespace is not None and self.namespace != ""

    def has_remote_node(self) -> bool:
        """Returns whether this spec has a remote node defined.

        Returns:
            bool:
                True if a remote node is defined, False otherwise.
        """
        return isinstance(self.remote_node, asyncua.Node)

    @override
    def get_remote_path(
        self,
        node: "DataModelNode | None" = None,
    ) -> str | None:
        """Returns the 'remote_path' used to interact with the remote node.

        Returns:
            str | None:
                Path used to interact with the remote node.
        """
        if self.remote_path is not None:
            return self.remote_path

        if node is not None:
            remote_path = ""
            if node.parent:
                parent_remote_path = node.parent.remote_path
                remote_path = parent_remote_path if parent_remote_path else ""
            if self.namespace:
                return remote_path + "/" + self.namespace + ":" + node.name
            return remote_path + "/" + node.name
        return None

    @override
    def inheritable_spec(self) -> "OpcuaRemoteResourceSpec":
        """Returns the inheritable part of this object.

        Returns a copy of this object containing only the properties that can be
        inherited by child nodes.

        Returns:
            OpcuaRemoteResourceSpec:
                Object with inheritable properties.
        """
        return OpcuaRemoteResourceSpec(
            namespace=self.namespace, node_id=self.node_id
        )

    @override
    def clone_for_child(self) -> "OpcuaRemoteResourceSpec":
        """Create an OPC UA spec for a child node.

        The parent's node id becomes the child's parent node id, preserving the
        inheritance behavior used by existing OPC UA data models.

        Returns:
            OpcuaRemoteResourceSpec:
                New OPC UA spec for the child node.
        """
        inheritable_spec = self.inheritable_spec()
        return OpcuaRemoteResourceSpec(
            namespace=inheritable_spec.namespace,
            remote_path=inheritable_spec.remote_path,
            parent_node_id=inheritable_spec.node_id,
        )

    @override
    def inherit_spec(self, parent: AbstractRemoteResourceSpec) -> None:
        """Inherits the properties from the given inheritable spec.

        Args:
            parent (AbstractRemoteResourceSpec):
                Inheritable spec to inherit properties from.
        """
        if not isinstance(parent, OpcuaRemoteResourceSpec):
            return
        if not self.has_parent_node_id() and parent.has_node_id():
            self.parent_node_id = parent.node_id
        if not self.has_namespace() and parent.has_namespace():
            self.namespace = parent.namespace

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            dict[str, Any]:
                Dictionary with all properties.
        """
        return {
            "remote_path": self.remote_path,
            "node_id": self.node_id,
            "namespace": self.namespace,
            "parent_node_id": self.parent_node_id,
            "remote_node": self.remote_node,
        }

    def __str__(self) -> str:
        return (
            "OpcuaRemoteResourceSpec("
            f"remote_path={self.remote_path!r}, "
            f"node_id={self.node_id!r}, "
            f"namespace={self.namespace!r}, "
            f"parent_node_id={self.parent_node_id!r}"
            ")"
        )

    def __repr__(self) -> str:
        return self.__str__()
