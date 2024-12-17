import uuid
from abc import ABC, abstractmethod
from typing import Iterator


class DataModelNode(ABC):
    """
    Abstract class for a node in the machine data model.

    Attributes:
        _id: The unique identifier of the node.
        _name: The name of the node.
        _description: The description of the node.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name: str = "" if name is None else name
        self._description = "" if description is None else description

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
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
    def __getitem__(self, child_name: str) -> "DataModelNode":
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
    def __iter__(self) -> Iterator["DataModelNode"]:
        """
        Iterate over the children of the node.
        :return: An iterator over the children of the node.
        """
        pass
