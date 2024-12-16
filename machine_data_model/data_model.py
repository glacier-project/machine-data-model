from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import ObjectVariableNode


class DataModel:

    def __init__(
        self,
        name: str = "",
        machine_category: str = "",
        machine_type: str = "",
        machine_model: str = "",
        description: str = "",
        root: FolderNode = None,
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
        self._nodes = {}
        self._build_nodes_map(self._root)

    @property
    def name(self):
        return self._name

    @property
    def machine_category(self):
        return self._machine_category

    @property
    def machine_type(self):
        return self._machine_type

    @property
    def machine_model(self):
        return self._machine_model

    @property
    def description(self):
        return self._description

    @property
    def root(self):
        return self._root

    def _build_nodes_map(self, node: FolderNode | ObjectVariableNode):
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

    def get_node_from_path(self, path: str):
        """
        Get a node from the data model by path.
        :param path: The path of the node to get from the data model.
        :return: The node with the specified path.
        """

        current_node = self._root
        if "/" not in path:
            if current_node.name == path:
                return current_node
            raise ValueError(f"Node with path '{path}' not found in data model")

        path_parts = path.split("/")[1:]
        for part in path_parts:
            if part == "":
                continue
            if not current_node.has_child(part):
                raise ValueError(f"Node with path '{path}' not found in data model")
            current_node = current_node[part]
        return current_node

    def get_node_from_id(self, node_id: str):
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

    def __str__(self):
        return (
            f"DataModel(name={self._name}, "
            f"machine_category={self._machine_category}, "
            f"machine_type={self._machine_type}, "
            f"machine_model={self._machine_model}, "
            f"description={self._description}, "
            f"root={self._root})"
        )

    def __repr__(self):
        return self.__str__()
