"""Lightweight handle binding a data-model node to a remote resource.

A :class:`RemoteResource` pairs a local :class:`DataModelNode` with the
connector that knows how to read or write it on a remote system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import weakref

from typing_extensions import override

if TYPE_CHECKING:
    from machine_data_model.nodes.data_model_node import DataModelNode

    from .abstract_remote_resource_spec import AbstractRemoteResourceSpec


class RemoteResource:
    """Connector-facing reference to a remote data model resource.

    The data model owns the generic node tree and optional protocol-specific
    specs. Connectors should receive a single resolved object instead of a loose
    pair of ``path`` and ``remote_resource_spec`` arguments.
    """

    __slots__ = ("_node_ref", "_node_type", "_path", "_spec")

    def __init__(
        self,
        path: str,
        spec: AbstractRemoteResourceSpec | None = None,
    ) -> None:
        """Create a resolved remote resource."""
        self._path = path
        self._spec = spec
        self._node_ref: weakref.ReferenceType[DataModelNode] | None = None
        self._node_type: type[DataModelNode] | None = None

    @property
    def path(self) -> str:
        """Return the connector-facing remote path."""
        return self._path

    @property
    def spec(self) -> AbstractRemoteResourceSpec | None:
        """Return the protocol-specific remote resource spec."""
        return self._spec

    @property
    def node(self) -> DataModelNode | None:
        """Return the owning data model node if it is still alive."""
        if self._node_ref is None:
            return None
        return self._node_ref()

    @property
    def node_type(self) -> type[DataModelNode] | None:
        """Return the owning node's type, even after the node is collected.

        The type is captured when the resource is built from a node so that
        decoding stays stable: a dropped weakref must not silently change how a
        payload is interpreted.
        """
        if self._node_type is not None:
            return self._node_type
        node = self.node
        return type(node) if node is not None else None

    @classmethod
    def from_node(cls, node: DataModelNode) -> RemoteResource:
        """Build a remote resource reference from a data model node."""
        spec = node.remote_resource_spec
        path = node.remote_path
        if path is None:
            if spec is None:
                raise ValueError(
                    "Remote nodes must define either a remote path or a "
                    "remote resource spec"
                )
            path = ""
        resource = cls(path=path, spec=spec)
        resource._node_ref = weakref.ref(node)
        resource._node_type = type(node)
        return resource

    @override
    def __repr__(self) -> str:
        return (
            "RemoteResource(" f"path={self.path!r}, " f"spec={self.spec!r}" ")"
        )
