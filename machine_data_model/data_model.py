from machine_data_model.nodes.data_model_node import DataModelNode
from typing import Any
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import ObjectVariableNode, VariableNode
from machine_data_model.nodes.method_node import MethodNode


class DataModel:
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
        self._build_nodes_map(self._root, True)

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

    def _build_nodes_map(
        self, node: FolderNode | ObjectVariableNode, is_root: bool = False
    ) -> None:
        """
        Build a map of nodes by id for fast access.
        :param node: The node to add to the map.
        :param is_root: A flag to indicate if the node is the root node.
        """
        if is_root:
            del self._nodes
            self._nodes = {}
        self._nodes[node.id] = node
        for child in node:
            # only folder and object nodes can have children
            if isinstance(child, (FolderNode, ObjectVariableNode)):
                self._build_nodes_map(child)
            elif isinstance(child, VariableNode):
                self._nodes[child.id] = child
            else:
                self._nodes[child.id] = child

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
        self._build_nodes_map(self._root, True)
        return True

    def remove_child(self, parent_id: str, child_id: str) -> bool:
        """
        Remove a child node from a parent node in the data model.
        """
        parent_node = self.get_node(parent_id)
        if not isinstance(parent_node, FolderNode):
            return False
        parent_node.remove_child(child_id)
        self._build_nodes_map(self._root, True)
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
            node.update(value)
            return True
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def call_method(self, method_id: str) -> Any:
        """
        Executes a method from the data model by exploring the structure of the node that contains that method.
        :param method_name: The id or the path of the method to call from the data model.
        :return: The return value of the method.
        """
        node = self.get_node(method_id)
        if isinstance(node, MethodNode):
            return node()
        raise ValueError(f"Method '{method_id}' not found in data model")

    def subscribe(self, target_node: str, subscriber: str) -> bool:
        node = self.get_node(target_node)
        if isinstance(node, VariableNode):
            node.subscribe(subscriber)
            return True
        raise ValueError(f"Variable Node '{target_node}' not found in data model")

    def unsubscribe(self, target_node: str, unsubscriber: str) -> bool:
        node = self.get_node(target_node)
        if isinstance(node, VariableNode):
            node.unsubscribe(unsubscriber)
            return True
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
