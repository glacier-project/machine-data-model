"""
A module defining the DataModel class and its associated methods for managing a
machine data model.
"""

from collections.abc import Callable
from typing import Any

from machine_data_model.behavior.local_execution_node import LocalExecutionNode
from machine_data_model.behavior.remote_execution_node import RemoteExecutionNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import MethodExecutionResult, MethodNode
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import ObjectVariableNode, VariableNode


class DataModel:
    """
    A DataModel represents the structure and data of a machine data model.
    """

    def __init__(
        self,
        name: str = "",
        machine_category: str = "",
        machine_type: str = "",
        machine_model: str = "",
        description: str = "",
        root: FolderNode | None = None,
    ):
        """
        Initialize the data model.

        Args:
            name (str, optional):
                The name of the data model. Defaults to "".
            machine_category (str, optional):
                The category of the machine. Defaults to "".
            machine_type (str, optional):
                The type of the machine. Defaults to "".
            machine_model (str, optional):
                The model of the machine. Defaults to "".
            description (str, optional):
                A description of the data model. Defaults to "".
            root (FolderNode | None, optional):
                The root folder node. If None, a default root is created.
                Defaults to None.

        """
        self._name = name
        self._machine_category = machine_category
        self._machine_type = machine_type
        self._machine_model = machine_model
        self._description = description
        self._root = (
            root
            if root is not None
            else FolderNode(name="root", description="Root folder of the data model")
        )
        # hashmap for fast access to nodes by id
        self._nodes: dict[str, DataModelNode] = {}
        self._register_nodes(self._root)

    @property
    def name(self) -> str:
        """
        Get the name of the data model.

        Returns:
            str:
                The name of the data model.

        """
        return self._name

    @property
    def machine_category(self) -> str:
        """
        Get the machine category.

        Returns:
            str:
                The machine category.

        """
        return self._machine_category

    @property
    def machine_type(self) -> str:
        """
        Get the machine type.

        Returns:
            str:
                The machine type.

        """
        return self._machine_type

    @property
    def machine_model(self) -> str:
        """
        Get the machine model.

        Returns:
            str:
                The machine model.

        """
        return self._machine_model

    @property
    def description(self) -> str:
        """
        Get the description of the data model.

        Returns:
            str:
                The description of the data model.

        """
        return self._description

    @property
    def root(self) -> FolderNode:
        """
        Get the root folder node.

        Returns:
            FolderNode:
                The root folder node.

        """
        return self._root

    def _register_node(self, node: DataModelNode) -> None:
        """
        Register a node in the data model for id-based access.

        Args:
            node (DataModelNode):
                The node to register in the data model.

        """
        self._nodes[node.id] = node
        node.set_data_model(self)

    def _resolve_local_cfg_nodes(self, node: DataModelNode) -> None:
        if not isinstance(node, CompositeMethodNode):
            return

        for cf_node in node.cfg.nodes():
            if isinstance(cf_node, RemoteExecutionNode):
                cf_node.sender_id = self._name
                continue

            assert isinstance(cf_node, LocalExecutionNode)

            if cf_node.is_node_static():
                ref_node = self.get_node(cf_node.node)
                assert isinstance(ref_node, DataModelNode)
                cf_node.set_ref_node(ref_node)
            else:
                # set get_node function to resolve the node at runtime
                cf_node.get_data_model_node = self.get_node

    def _register_nodes(self, node: FolderNode | ObjectVariableNode) -> None:
        """
        Register all nodes in the data model for id-based access.

        Args:
            node (FolderNode | ObjectVariableNode):
                The node to start registering from.

        """
        del self._nodes
        self._nodes = {}

        def _f_(n: DataModelNode) -> None:
            self._register_node(n)
            self._resolve_local_cfg_nodes(n)

        self.traverse(node, _f_)

    def traverse(
        self,
        node: FolderNode | ObjectVariableNode,
        function: Callable[[DataModelNode], None],
    ) -> None:
        """
        Traverse the data model and apply a function to each node.

        Args:
            node (FolderNode | ObjectVariableNode):
                The node to start the traversal from.
            function (Callable[[DataModelNode], None]):
                The function to apply to each node.

        """
        function(node)
        for child in node:
            if isinstance(child, FolderNode):
                self.traverse(child, function)
            elif isinstance(child, ObjectVariableNode):
                function(child)
                self.traverse(child, function)
            else:
                function(child)

    def _get_node_from_path(self, path: str) -> DataModelNode | None:
        """
        Get a node from the data model by path.

        Args:
            path (str):
                The path of the node to get from the data model.

        Returns:
            DataModelNode | None:
                The node with the specified path, or None if not found.

        """
        current_node: DataModelNode = self._root
        path = path.lstrip("/")
        if "/" not in path:
            if current_node.name == path:
                return current_node
            return None

        path_parts = path.split("/")[1:]
        for part in path_parts:
            if part == "":
                continue
            if isinstance(current_node, FolderNode) and not current_node.has_child(
                part
            ):
                return None
            if isinstance(
                current_node, ObjectVariableNode
            ) and not current_node.has_property(part):
                return None
            current_node = current_node[part]
        return current_node

    def _get_node_from_id(self, node_id: str) -> DataModelNode | None:
        """
        Get a node from the data model by id.

        Args:
            node_id (str):
                The id of the node to get from the data model.

        Returns:
            DataModelNode | None:
                The node with the specified id, or None if not found.

        """
        if node_id not in self._nodes:
            return None
        return self._nodes[node_id]

    def add_child(self, parent_id: str, child: DataModelNode) -> bool:
        """
        Add a child node to a parent node in the data model.

        Args:
            parent_id (str):
                The id of the parent node.
            child (DataModelNode):
                The child node to add.

        Returns:
            bool:
                True if the child was added successfully, False otherwise.

        """
        parent_node = self.get_node(parent_id)
        if not isinstance(parent_node, FolderNode):
            return False
        parent_node.add_child(child)
        return True

    def remove_child(self, parent_id: str, child_id: str) -> bool:
        """
        Remove a child node from a parent node in the data model.

        Args:
            parent_id (str):
                The id of the parent node.
            child_id (str):
                The id of the child node to remove.

        Returns:
            bool:
                True if the child was removed successfully, False otherwise.

        """
        parent_node = self.get_node(parent_id)
        if not isinstance(parent_node, FolderNode):
            return False
        parent_node.remove_child(child_id)
        return True

    def get_node(self, node_id: str) -> DataModelNode | None:
        """
        Get a node from the data model by its id or path.

        Args:
            node_id (str):
                The id or path of the node to get from the data model.

        Returns:
            DataModelNode | None:
                The node with the specified id or path, or None if not found.

        """
        if "/" not in node_id:
            return self._get_node_from_id(node_id)
        return self._get_node_from_path(node_id)

    def read_variable(self, variable_id: str) -> Any:
        """
        Read a variable from the data model by exploring the structure of the
        node that contains that variable.

        Args:
            variable_id (str):
                The id or the path of the variable to read from the data model.

        Returns:
            Any:
                The value of the variable.

        Raises:
            ValueError:
                If the variable is not found in the data model.

        """
        node = self.get_node(variable_id)
        if isinstance(node, VariableNode):
            return node.read()
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def write_variable(self, variable_id: str, value: Any) -> bool:
        """
        Write a variable to the data model by exploring the structure of the
        node that contains that variable.

        Args:
            variable_id (str):
                The id or the path of the variable to write to the data model.
            value (Any):
                The value to write to the variable.

        Returns:
            bool:
                True if the variable was written successfully, False otherwise.

        Raises:
            ValueError:
                If the variable is not found in the data model.

        """
        node = self.get_node(variable_id)
        if isinstance(node, VariableNode):
            return node.write(value)
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def call_method(self, method_id: str) -> MethodExecutionResult:
        """
        Executes a method from the data model by exploring the structure of the
        node that contains that method.

        Args:
            method_id (str):
                The id or the path of the method to call from the data model.

        Returns:
            MethodExecutionResult:
                The result of the method execution.

        Raises:
            ValueError:
                If the method is not found in the data model.

        """
        node = self.get_node(method_id)
        if isinstance(node, MethodNode):
            return node()
        raise ValueError(f"Method '{method_id}' not found in data model")

    def subscribe(self, target_node: str, subscription: VariableSubscription) -> bool:
        """
        Adds the provided subscription to the target variable node in the data
        model.

        Args:
            target_node (str):
                The id or the path of the variable node to subscribe to.
            subscription (VariableSubscription):
                The subscription to add to the variable node.

        Returns:
            bool:
                True if the subscription was added successfully, False
                otherwise.

        Raises:
            ValueError:
                If the target node is not found or is not a VariableNode.

        """
        node = self.get_node(target_node)
        if isinstance(node, VariableNode):
            return node.subscribe(subscription)
        raise ValueError(f"Variable Node '{target_node}' not found in data model")

    def unsubscribe(self, target_node: str, subscription: VariableSubscription) -> bool:
        """
        Removes the provided subscription from the target variable node in the
        data model.

        Args:
            target_node (str):
                The id or the path of the variable node to unsubscribe from.
            subscription (VariableSubscription):
                The subscription to remove from the variable node.

        Returns:
            bool:
                True if the subscription was removed successfully, False
                otherwise.

        Raises:
            ValueError:
                If the target node is not found or is not a VariableNode.

        """
        node = self.get_node(target_node)
        if isinstance(node, VariableNode):
            return node.unsubscribe(subscription)
        raise ValueError(f"Variable Node '{target_node}' not found in data model")

    def __str__(self) -> str:
        return (
            f"DataModel(name={self._name}, "
            f"machine_category={self._machine_category}, "
            f"machine_type={self._machine_type}, "
            f"machine_model={self._machine_model}, "
            f"description={self._description}, "
            f"root={self._root})"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if not isinstance(other, DataModel):
            return False
        return (
            self._name == other._name
            and self._machine_category == other._machine_category
            and self._machine_type == other._machine_type
            and self._machine_model == other._machine_model
            and self._description == other._description
            and self._root == other._root
        )
