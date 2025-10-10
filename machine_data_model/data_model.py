"""
A module defining the DataModel class and its associated methods for managing a
machine data model.
"""

import weakref
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
        return self._name

    @property
    def machine_category(self) -> str:
        return self._machine_category

    @property
    def machine_type(self) -> str:
        return self._machine_type

    @property
    def machine_model(self) -> str:
        return self._machine_model

    @property
    def description(self) -> str:
        return self._description

    @property
    def root(self) -> FolderNode:
        return self._root

    def _register_node(self, node: DataModelNode) -> None:
        """
        Register a node in the data model for id-based access.
        :param node: The node to register in the data model.
        """
        self._nodes[node.id] = node
        node._data_model = weakref.ref(self)

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
        :param node: The node to register in the data model.
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
        :param node: The node to start the traversal from.
        :param function: The function to apply to each node.
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
        :param path: The path of the node to get from the data model.
        :return: The node with the specified path.
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
        :param node_id: The id of the node to get from the data model.
        :return: The node with the specified id.
        """
        if node_id not in self._nodes:
            return None
        return self._nodes[node_id]

    def add_child(self, parent_id: str, child: DataModelNode) -> bool:
        """
        Add a child node to a parent node in the data model.
        """
        parent_node = self.get_node(parent_id)
        if not isinstance(parent_node, FolderNode):
            return False
        parent_node.add_child(child)
        return True

    def remove_child(self, parent_id: str, child_id: str) -> bool:
        """
        Remove a child node from a parent node in the data model.
        """
        parent_node = self.get_node(parent_id)
        if not isinstance(parent_node, FolderNode):
            return False
        parent_node.remove_child(child_id)
        return True

    def get_node(self, node_id: str) -> DataModelNode | None:
        """
        Get a node from the data model by its id or path.
        :param node_id: The id or path of the node to get from the data model.
        :return: The node with the specified id or path.
        """
        if "/" not in node_id:
            return self._get_node_from_id(node_id)
        return self._get_node_from_path(node_id)

    def read_variable(self, variable_id: str) -> Any:
        """
        Read a variable from the data model by exploring the structure of the node that contains that variable.
        :param variable_id: The id or the path of the variable to read from the data model.
        :return: The value of the variable.
        """
        node = self.get_node(variable_id)
        if isinstance(node, VariableNode):
            return node.read()
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def write_variable(self, variable_id: str, value: Any) -> bool:
        """
        Write a variable to the data model by exploring the structure of the node that contains that variable.
        :param variable_id: The id or the path of the variable to write to the data model.
        :param value: The value to write to the variable.
        :return: True if the variable was written successfully, False otherwise.
        """
        node = self.get_node(variable_id)
        if isinstance(node, VariableNode):
            return node.write(value)
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def call_method(self, method_id: str) -> MethodExecutionResult:
        """
        Executes a method from the data model by exploring the structure of the node that contains that method.
        :param method_name: The id or the path of the method to call from the data model.
        :return: The result of the method execution.
        """
        node = self.get_node(method_id)
        if isinstance(node, MethodNode):
            return node()
        raise ValueError(f"Method '{method_id}' not found in data model")

    def subscribe(self, target_node: str, subscription: VariableSubscription) -> bool:
        """
        Adds the provided subscription to the target variable node in the data model.
        Raises a ValueError if the target node is not found or is not a VariableNode.

        :param target_node: The id or the path of the variable node to subscribe to.
        :param subscription: The subscription to add to the variable node.
        :return: True if the subscription was added successfully, False otherwise.
        """
        node = self.get_node(target_node)
        if isinstance(node, VariableNode):
            return node.subscribe(subscription)
        raise ValueError(f"Variable Node '{target_node}' not found in data model")

    def unsubscribe(self, target_node: str, subscription: VariableSubscription) -> bool:
        """
        Removes the provided subscription from the target variable node in the data model.
        Raises a ValueError if the target node is not found or is not a VariableNode.

        :param target_node: The id or the path of the variable node to unsubscribe from.
        :param subscription: The subscription to remove from the variable node.
        :return: True if the subscription was removed successfully, False otherwise.
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
