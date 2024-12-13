from typing_extensions import override

from machine_data_model.nodes.data_model_node import DataModelNode


class FolderNode(DataModelNode):
    """
    A FolderNode class is a node that represents a folder in the machine data model.
    Folders of the machine data model are used to organize the node of the machine data
    model in a hierarchical structure.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new FolderNode instance.
        :param kwargs: A dictionary containing the attributes of the folder node.
        The dictionary may contain the following keys:
            - id: The unique identifier of the folder.
            - name: The name of the folder.
            - description: The description of the folder.
            - children: A dictionary of child nodes of the folder.
        """
        super().__init__(**kwargs)
        self._children = kwargs.get("children", {})

    @property
    def children(self):
        return self._children

    def add_child(self, child: DataModelNode):
        """
        Add a child node to the folder.
        :param child: The child node to add to the folder.
        """
        assert isinstance(child, DataModelNode)
        self._children[child.name] = child

    def remove_child(self, child_name: str):
        """
        Remove a child node from the folder.
        :param child_name: The name of the child node to remove from the folder.
        """
        if child_name in self._children:
            del self._children[child_name]
        else:
            raise ValueError(
                f"Child node with name '{child_name}' not found in folder '{self.name}'"
            )

    def has_child(self, child_name: str) -> bool:
        """
        Check if the folder has a child node with the specified name.
        :param child_name: The name of the child node to check.
        :return: True if the folder has a child node with the specified name, False
            otherwise.
        """
        return child_name in self._children

    @override
    def __getitem__(self, child_name: str):
        """
        Get a child node from the folder by name.
        :param child_name: The name of the child node to get from the folder.
        :return: The child node with the specified name.
        """
        return self._children[child_name]

    @override
    def __contains__(self, child_name: str) -> bool:
        """
        Check if the folder has a child node with the specified name.
        :param child_name: The name of the child node to check.
        :return: True if the folder has a child node with the specified name, False
            otherwise.
        """
        return self.has_child(child_name)

    @override
    def __iter__(self):
        """
        Iterate over the children of the folder.
        :return: An iterator over the children of the folder.
        """
        children = self._children
        for child in children:
            yield children[child]

    def __str__(self):
        return (
            f"FolderNode(id={self._id}, name={self._name}, "
            f"description={self._description}, children={self._children})"
        )

    def __repr__(self):
        return self.__str__()
