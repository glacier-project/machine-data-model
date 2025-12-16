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
        pass

    @abstractmethod
    def build_read_variable_response_message(
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a read variable response message.

        Args:
            target (str): The target of the message.
            node (str): The node that was read.
            value (Any): The value of the node.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed read variable response message.
        """
        pass

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
        pass

    @abstractmethod
    def build_write_variable_response_message(
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a write variable response message.

        Args:
            target (str): The target of the message.
            node (str): The node that was written.
            value (Any): The value that was written to the node.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed write variable response message.
        """
        pass

    @abstractmethod
    def build_subscribe_variable_message(
        self, target: str, node: str, correlation_id: str | None = None
    ) -> Message:
        """Build a subscribe message for the specified variable.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be subscribed to.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed subscribe message.
        """
        pass

    @abstractmethod
    def build_subscribe_variable_response_message(
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a subscribe variable response message.

        Args:
            target (str): The target of the message.
            node (str): The node that was subscribed to.
            value (Any): The value of the node.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed subscribe variable response message.
        """
        pass

    @abstractmethod
    def build_data_change_subscription_message(
        self,
        target: str,
        node: str,
        deadband: float,
        is_percent: bool,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a data change subscription message.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be subscribed to.
            deadband (float): The deadband value for the subscription.
            is_percent (bool): Whether the deadband is a percentage.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed data change subscription message.
        """
        pass

    @abstractmethod
    def build_in_range_subscription_message(
        self,
        target: str,
        node: str,
        low: float,
        high: float,
        correlation_id: str | None = None,
    ) -> Message:
        """Build an in-range subscription message.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be subscribed to.
            low (float): The low threshold for the subscription.
            high (float): The high threshold for the subscription.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed in-range subscription message.
        """
        pass

    @abstractmethod
    def build_out_of_range_subscription_message(
        self,
        target: str,
        node: str,
        low: float,
        high: float,
        correlation_id: str | None = None,
    ) -> Message:
        """Build an out-of-range subscription message.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be subscribed to.
            low (float): The low threshold for the subscription.
            high (float): The high threshold for the subscription.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed out-of-range subscription message.
        """
        pass

    @abstractmethod
    def build_unsubscribe_variable_message(
        self, target: str, node: str, correlation_id: str | None = None
    ) -> Message:
        """Build an unsubscribe message for the specified variable.

        Args:
            target (str): The target of the message.
            node (str): The path of the variable to be unsubscribed from.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed unsubscribe message.
        """
        pass

    @abstractmethod
    def build_unsubscribe_variable_response_message(
        self, target: str, node: str, correlation_id: str | None = None
    ) -> Message:
        """Build an unsubscribe variable response message.

        Args:
            target (str): The target of the message.
            node (str): The node that was unsubscribed from.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed unsubscribe variable response message.
        """
        pass

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
        pass

    @abstractmethod
    def build_method_completed_message(
        self,
        target: str,
        node: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        ret: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a method completed message with the specified parameters.

        Args:
            target (str): The target of the message.
            node (str): The method node that was invoked.
            args (list[Any] | None): The positional arguments for the method.
            kwargs (dict[str, Any] | None): The keyword arguments for the
            method.
            ret (dict[str, Any] | None): The return values from the method.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed method completed message.
        """
        pass

    @abstractmethod
    def build_method_started_message(
        self,
        target: str,
        node: str,
        ret: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a method started message with the specified parameters.

        Args:
            target (str): The target of the message.
            node (str): The method node that was invoked.
            ret (dict[str, Any] | None): The return values from the method.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed method started message.
        """
        pass

    @abstractmethod
    def build_variable_update_message(
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> Message:
        """Build a variable update message.

        Args:
            target (str): The target of the message.
            node (str): The variable node that was updated.
            value (Any): The new value of the variable.
            correlation_id (str | None): Optional correlation ID.

        Returns:
            The constructed variable update message.
        """
        pass
