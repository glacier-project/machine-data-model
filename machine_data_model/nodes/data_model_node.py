import uuid
from abc import ABC, abstractmethod


class DataModelNode(ABC):
    """
    Abstract class for a node in the machine data model.

    Attributes:
        _id: The unique identifier of the node.
        _name: The name of the node.
        _description: The description of the node.
    """

    def __init__(self, **kwargs):
        self._id = kwargs.get("id", uuid.uuid4())
        self._name = kwargs.get("name", "Unnamed Node")
        self._description = kwargs.get("description", "")

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    # @abstractmethod
    # def has_child(self, child_name: str) -> bool:
    #     """
    #     Check if the node has a child node with the specified name.
    #     :param child_name: The name of the child node to check.
    #     :return: True if the node has a child node with the specified name, False
    #         otherwise.
    #     """
    #     pass

    @abstractmethod
    def __getitem__(self, child_name: str):
        """
        Get a child node from the node by name.
        :param child_name: The name of the child node to get from the node.
        :return: The child node with the specified name.
        """
        pass

    @abstractmethod
    def __contains__(self, child_name: str) -> bool:
        """
        Check if the node has a child node with the specified name.
        :param child_name: The name of the child node to check.
        :return: True if the node has a child node with the specified name, False
            otherwise.
        """
        pass

    @abstractmethod
    def __iter__(self):
        """
        Iterate over the children of the node.
        :return: An iterator over the children of the node.
        """
        pass
