from abc import ABC, abstractmethod

from typing_extensions import Any

from machine_data_model.data_model import DataModel
from dataclasses import dataclass

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import VariableNode


@dataclass(init=True, slots=True)
class Message(ABC):
    """
    Abstract base class representing a message in the protocol.
    """

    pass


class ProtocolMng(ABC):
    """
    Abstract class responsible for handling messages encoded with a specific protocol
    and updating the machine data model accordingly.

    :ivar _data_model: The machine data model that is updated based on the processed messages.
    """

    def __init__(self, data_model: DataModel):
        """
        Initializes the ProtocolMng with a specific machine data model.

        :param data_model: The machine data model to be used for updating based on the processed messages.
        """

        self._data_model = data_model
        data_model.traverse(data_model.root, self._set_variable_callback)

    def _set_variable_callback(self, node: DataModelNode) -> None:
        """
        Set the callback function for notifying the protocol manager of variable updates.

        :param node: The node to set the callback for.
        :return: The node with the callback set.
        """
        if not isinstance(node, VariableNode):
            return

        node.set_subscription_callback(self._update_variable_callback)

    @abstractmethod
    def handle_request(self, msg: Message) -> Message:
        """
        Abstract method to handle a protocol-specific request and update the
        machine data model.

        :param msg: The request message to be handled, which should be an instance of the appropriate protocol message.
        :return: A response message based on the handling of the input message.
        """

        pass

    def get_data_model(self) -> DataModel:
        """
        Returns the machine data model.

        :return: The current machine data model used by the protocol manager.
        """
        return self._data_model

    @abstractmethod
    def _update_variable_callback(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """
        Handle the update and create the corresponding Message.

        This method is called when an update to a variable occurs. It constructs
        a `GlacierMessage` with the relevant details, including the sender,
        target, and payload, and appends it to the list of update messages.
        """
        pass

    @abstractmethod
    def resume_composite_method(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        pass
