import uuid


class DataModelNode:
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
