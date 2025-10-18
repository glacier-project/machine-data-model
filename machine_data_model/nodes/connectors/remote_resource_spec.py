from abc import ABC, abstractmethod
from typing import Any
from typing_extensions import override
from ..data_model_node import DataModelNode


class RemoteResourceSpec(ABC):
    """
    Represents node properties that are specific for a certain protocol.
    """

    def __init__(self, parent: "DataModelNode | None", remote_path: str | None = None):
        self._parent = parent
        self._remote_path = remote_path

    @property
    def parent(self) -> "DataModelNode | None":
        return self._parent

    @parent.setter
    def parent(self, value: "DataModelNode | None") -> None:
        self._parent = value

    def remote_path(self) -> str | None:
        """
        Returns the 'remote_path'.
        """
        return self._remote_path

    @abstractmethod
    def inheritable_spec(self) -> "RemoteResourceSpec":
        """
        Returns a copy of this object, where the only properties that get copied
        are properties that will be inherited by child nodes.
        """
        pass

    @abstractmethod
    def merge_specs(self, spec1: Any, spec2: Any) -> Any:
        """
        Creates a third object which has the combined properties of spec1 and spec2.
        > Note that spec1 has priority over spec2: spec1's properties override spec2's
        > properties when the properties are defined for both objects.
        """
        pass


class OpcuaRemoteResourceSpec(RemoteResourceSpec):
    """
    Represents node properties that are specific for the OPC UA protocol.
    """

    def __init__(
        self,
        parent: "DataModelNode | None" = None,
        remote_path: str | None = None,
        node_id: str | None = None,
        namespace: str | None = None,
    ) -> None:
        super().__init__(parent=parent, remote_path=remote_path)
        self._node_id: str | None = node_id
        self._namespace: str | None = namespace

    @override
    def remote_path(self) -> str | None:
        """
        Returns 'remote_path' when defined,
        otherwise it returns the 'node_id'.
        If both are undefined, it tries
        """
        if self._remote_path is not None:
            return self._remote_path

        if self._node_id is not None:
            return self._node_id

        if self._parent:
            remote_path = ""
            if self._parent.parent:
                parent_remote_path = self._parent.parent.remote_path
                remote_path = parent_remote_path if parent_remote_path else ""
            if self._namespace:
                return remote_path + "/" + self._namespace + ":" + self._parent.name
            else:
                return remote_path + "/" + self._parent.name

        return None

    @override
    def inheritable_spec(self) -> "OpcuaRemoteResourceSpec":
        """
        Returns a copy of this object, where the only properties that get copied
        are properties that will be inherited by child nodes.
        """
        return OpcuaRemoteResourceSpec(namespace=self._namespace)

    @override
    def merge_specs(
        self, spec1: "OpcuaRemoteResourceSpec", spec2: "OpcuaRemoteResourceSpec"
    ) -> "OpcuaRemoteResourceSpec":
        """
        Creates a third object which has the combined properties of spec1 and spec2.
        > Note that spec1 has priority over spec2: spec1's properties override spec2's
        > properties when the properties are defined for both objects.
        """
        assert isinstance(
            spec1, OpcuaRemoteResourceSpec
        ), "spec1 must be a OpcuaRemoteResourceSpec"
        assert isinstance(
            spec2, OpcuaRemoteResourceSpec
        ), "spec2 must be a OpcuaRemoteResourceSpec"
        new_spec = OpcuaRemoteResourceSpec()
        new_spec._parent = spec1._parent if spec1._parent else spec2._parent
        new_spec._remote_path = (
            spec1._remote_path if spec1._remote_path else spec2._remote_path
        )
        new_spec._node_id = spec1._node_id if spec1._node_id else spec2._node_id
        new_spec._namespace = spec1._namespace if spec1._namespace else spec2._namespace
        return new_spec

    def __str__(self) -> str:
        return (
            "OpcuaRemoteResourceSpec("
            f"remote_path={repr(self.remote_path)}, "
            f"node_id={repr(self._node_id)}, "
            f"namespace={repr(self._namespace)}"
            ")"
        )

    def __repr__(self) -> str:
        return self.__str__()
