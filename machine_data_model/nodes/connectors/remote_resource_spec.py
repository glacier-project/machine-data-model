"""Remote Resource Spec.

This module defines the RemoteResourceSpec abstract class.
It used to define all the properties of a DataModelNode that
are connector/protocol specific.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from machine_data_model.nodes.data_model_node import DataModelNode


class RemoteResourceSpec(ABC):
    """Represents node properties that are specific for a certain protocol."""

    def __init__(
        self, parent: "DataModelNode | None", remote_path: str | None = None
    ):
        """Constructor.

        Args:
            parent (DataModelNode | None):
                Node which owns these properties.
            remote_path (str | None, optional):
                Node's remote path.
        """
        self._parent = parent
        self._remote_path = remote_path

    @property
    def parent(self) -> "DataModelNode | None":
        return self._parent

    @parent.setter
    def parent(self, value: "DataModelNode | None") -> None:
        self._parent = value

    def remote_path(self) -> str | None:
        """Returns the 'remote_path'.

        Returns:
            str | None:
                Node's remote path
        """
        return self._remote_path

    @abstractmethod
    def inheritable_spec(self) -> "RemoteResourceSpec":
        """Returns a copy of this object, where the only properties that get
        copied are properties that will be inherited by child nodes.

        Returns:
            RemoteResourceSpec:
                Object with inheritable properties.
        """
        pass

    @abstractmethod
    def merge_specs(self, spec1: Any, spec2: Any) -> Any:
        """Creates a third object which has the combined properties of spec1 and
        spec2.
        > Note that spec1 has priority over spec2: spec1's properties override
        spec2's properties when the properties are defined for both objects.

        Args:
            spec1 (Any):
                First object to be merged.
            spec2 (Any):
                Second object to be merged.

        Returns:
            Any:
                Object with merged properties of both spec1 and spec2.
        """
        pass
