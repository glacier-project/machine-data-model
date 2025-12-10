from abc import ABC, abstractmethod
from typing import Any

from machine_data_model.protocols.message import Message


class MessageBuilder(ABC):
    """Message builder base class.

    Abstract base class for building and parsing messages in a communication
    protocol.

    Attributes:
        _sender (str): The sender of the message.
    """

    def __init__(self, sender: str):
        """Initializes the MessageBuilder with a specific sender.

        Args:
            sender (str): The sender of the message.
        """
        self._sender = sender

    def get_sender(self) -> str:
        """Return the sender of the message.

        Returns:
            The sender of the message.
        """
        return self._sender

    def set_sender(self, sender: str) -> None:
        """Set the sender of the message.

        Args:
            sender (str): The sender of the message.
        """
        self._sender = sender

    @abstractmethod
    def build_read_variable_message(self, target: str, node: str) -> Message:
        """Build a read message for the specified variable.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be read.

        Returns:
            The constructed read message.
        """
        pass  # To be implemented in subclasses

    @abstractmethod
    def build_write_variable_message(
        self, target: str, node: str, value: Any
    ) -> Message:
        """Build a write message for the specified variable and value.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be written.
            value (Any): The value to be written to the variable.

        Returns:
            The constructed write message.
        """
        pass  # To be implemented in subclasses

    @abstractmethod
    def build_invoke_method_message(
        self,
        target: str,
        node: str,
        correlation_id: str | None = None,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Message:
        """Build an invoke method message with the specified parameters.

        Args:
            target (str): The target of the message.
            node (str): The method node to be invoked.
            correlation_id (str | None): Optional correlation ID.
            args (list[Any] | None): The positional arguments for the method.
            kwargs (dict[str, Any] | None): The keyword arguments for the
            method.

        Returns:
            The constructed invoke method message.
        """
        pass  # To be implemented in subclasses
