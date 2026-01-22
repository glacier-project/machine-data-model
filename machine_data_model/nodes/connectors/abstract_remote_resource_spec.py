"""Remote Resource Spec.

This module defines the RemoteResourceSpec abstract class.
It used to define all the properties of a DataModelNode that
are connector/protocol specific.
"""

from abc import ABC, abstractmethod

from machine_data_model.nodes.data_model_node import DataModelNode


class AbstractRemoteResourceSpec(ABC):
    """Represents node properties that are specific for a certain protocol."""

    def __init__(
        self, parent: DataModelNode | None, remote_path: str | None = None
    ):
        """Constructor.

        Args:
            parent (DataModelNode | None):
                Node which owns these properties.
            remote_path (str | None, optional):
                Node's remote path.
        """
        self.parent = parent
        self.remote_path = remote_path

    def has_parent(self) -> bool:
        """Returns whether this spec has a parent node defined.

        Returns:
            bool:
                True if a parent node is defined, False otherwise.
        """
        return isinstance(self.parent, DataModelNode)

    def has_path(self) -> bool:
        """Returns whether this spec has a remote path defined.

        Returns:
            bool:
                True if a remote path is defined, False otherwise.
        """
        return self.remote_path is not None and self.remote_path != ""

    @abstractmethod
    def inheritable_spec(self) -> "AbstractRemoteResourceSpec":
        """Returns the inheritable part of this object.

        Returns a copy of this object containing only the properties that can be
        inherited by child nodes.

        Returns:
            AbstractRemoteResourceSpec:
                Object with inheritable properties.
        """
        pass

    @abstractmethod
    def inherit_spec(self, parent: "AbstractRemoteResourceSpec") -> None:
        """Inherits properties from another spec.

        Args:
            parent (AbstractRemoteResourceSpec):
                Parent spec to inherit properties from.
        """
        pass

    @abstractmethod
    def get_remote_path(self) -> str | None:
        """Returns the remote path of this resource spec.

        Returns:
            str | None:
                Remote path if defined, None otherwise.
        """
        pass
