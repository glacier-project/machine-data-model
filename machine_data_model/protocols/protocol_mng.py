"""
Protocol manager base classes.

This module defines the base ProtocolMng class that provides the interface for
handling protocol-specific messages and managing communication with the machine
data model.
"""

from abc import ABC, abstractmethod
from typing import Any

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.message import Message


class ProtocolMng(ABC):
    """
    Abstract class responsible for handling messages encoded with a specific
    protocol and updating the machine data model accordingly.

    Attributes:
        _data_model (DataModel):
            The machine data model that is updated based on the processed
            messages.

    """

    def __init__(self, data_model: DataModel):
        """
        Initializes the ProtocolMng with a specific machine data model.

        Args:
            data_model (DataModel):
                The machine data model to be used for updating based on the
                processed messages.

        """
        self._data_model = data_model
        data_model.traverse(data_model.root, self._set_variable_callback)

    def _set_variable_callback(self, node: DataModelNode) -> None:
        """
        Set the callback function for notifying the protocol manager of variable
        updates.

        Args:
            node (DataModelNode):
                The node to set the callback for.

        Returns:
            None:
                The node with the callback set.

        """
        if not isinstance(node, VariableNode):
            return

        node.set_subscription_callback(self._update_variable_callback)

    @abstractmethod
    def handle_request(self, msg: Message) -> Message | None:
        """
        Abstract method to handle a protocol-specific request and update the
        machine data model.

        Args:
            msg (Message):
                The request message to be handled, which should be an instance
                of the appropriate protocol message.

        Returns:
            Message | None:
                A response message based on the handling of the input message.

        """

    def get_data_model(self) -> DataModel:
        """
        Returns the machine data model.

        Returns:
            DataModel:
                The current machine data model used by the protocol manager.

        """
        return self._data_model

    @abstractmethod
    def _update_variable_callback(
        self, subscription: VariableSubscription, node: VariableNode, value: Any
    ) -> None:
        """
        Handle the update and create the corresponding Message.

        This method is called when an update to a variable occurs. It constructs
        a `GlacierMessage` with the relevant details, including the sender,
        target, and payload, and appends it to the list of update messages.
        """

    @abstractmethod
    def resume_composite_method(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """
        Abstract method to resume a composite method execution.

        Args:
            subscriber (str):
                The subscriber identifier.
            node (VariableNode):
                The variable node associated with the composite method.
            value (Any):
                The value that triggered the resume.

        """
