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
        self._build_nodes_map(self._root)
        # TODO: add message handler

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

    def _build_nodes_map(self, node: FolderNode | ObjectVariableNode) -> None:
        """
        Build a map of nodes by id for fast access.
        :param node: The node to add to the map.
        """
        self._nodes[node.id] = node
        for child in node:
            # only folder and object nodes can have children
            if isinstance(child, (FolderNode, ObjectVariableNode)):
                self._build_nodes_map(child)
            else:
                self._nodes[child.id] = child

    def get_node_from_path(self, path: str) -> DataModelNode:
        """
        Get a node from the data model by path.
        :param path: The path of the node to get from the data model.
        :return: The node with the specified path.
        """

        current_node: DataModelNode = self._root
        if "/" not in path:
            if current_node.name == path:
                return current_node
            raise ValueError(f"Node with path '{path}' not found in data model")

        path_parts = path.split("/")[1:]
        for part in path_parts:
            if part == "":
                continue
            if isinstance(current_node, FolderNode) and not current_node.has_child(
                part
            ):
                raise ValueError(f"Node with path '{path}' not found in data model")
            if isinstance(
                current_node, ObjectVariableNode
            ) and not current_node.has_property(part):
                raise ValueError(f"Node with path '{path}' not found in data model")
            current_node = current_node[part]
        return current_node

    def get_node_from_id(self, node_id: str) -> DataModelNode:
        """
        Get a node from the data model by id.
        :param node_id: The id of the node to get from the data model.
        :return: The node with the specified id.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node with id '{node_id}' not found in data model")
        return self._nodes[node_id]

    # TODO: implement the methods needed to read, write, call the methods, and
    #       serialize/deserialize the data model
    def read_variable(self, variable_id: str) -> Any:
        """
        Read a variable from the data model by exploring the structure of the node that contains that variable.
        :param variable_id: The name of the variable to read from the data model.
        :return: The value of the variable.
        """
        node = self.get_node_from_id(variable_id)
        if isinstance(node, VariableNode):
            return node._read_value()
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def write_variable(self, variable_id: str, value: Any) -> bool:
        """
        Write a variable to the data model by exploring the structure of the node that contains that variable.
        :param variable_id: The name of the variable to write to the data model.
        :param value: The value to write to the variable.
        :return: True if the variable was written successfully, False otherwise.
        """
        node = self.get_node_from_id(variable_id)
        if isinstance(node, VariableNode):
            node._update_value(value)
            return True
        raise ValueError(f"Variable '{variable_id}' not found in data model")

    def call_method(self, method_id: str, *args: Any) -> Any:
        """
        Call a method from the data model by exploring the structure of the node that contains that method.
        :param method_id: The name of the method to call from the data model.
        :param args: The arguments to pass to the method.
        :return: The return value of the method.
        """
        node = self.get_node_from_id(method_id)
        if isinstance(node, MethodNode):
            return node.callback(*args)
        raise ValueError(f"Method '{method_id}' not found in data model")

    def serialize(self) -> dict:
        """
        Serialize the data model to a dictionary.
        :return: A dictionary representation of the data model.
        """
        return {
            "name": self._name,
            "machine_category": self._machine_category,
            "machine_type": self._machine_type,
            "machine_model": self._machine_model,
            "description": self._description,
            "root": self._root,
        }

    @staticmethod
    def deserialize(data: dict) -> "DataModel":
        """
        Deserialize a dictionary to a data model.
        :param data: The dictionary to deserialize to a data model.
        :return: A data model instance.
        """
        return DataModel(
            name=data["name"],
            machine_category=data["machine_category"],
            machine_type=data["machine_type"],
            machine_model=data["machine_model"],
            description=data["description"],
            root=data["root"],
        )

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
