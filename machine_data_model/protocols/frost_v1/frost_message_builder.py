import uuid
from machine_data_model.protocols.message_builder import MessageBuilder
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
    ProtocolMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    VariablePayload,
    SubscriptionPayload,
    DataChangeSubscriptionPayload,
    InRangeSubscriptionPayload,
    OutOfRangeSubscriptionPayload,
    MethodPayload,
    ProtocolPayload,
    ErrorPayload,
    ErrorCode,
    ErrorMessages,
)
from typing import Any
from typing_extensions import override


class FrostMessageBuilder(MessageBuilder):
    """
    Builder class for creating Frost protocol messages.

    Attributes:
        - sender (str):
            The sender of the message.
        - protocol_version (tuple):
            The version of the protocol.
    """

    def __init__(
        self,
        sender: str,
        protocol_version: tuple = (1, 0, 0),
    ):
        """
        Initializes the FrostMessageBuilder.

        Args:
            - sender (str):
                The sender of the message.
            - protocol_version (tuple):
                The version of the protocol.
        """
        super().__init__(sender)
        self._protocol_version: tuple[int, int, int] = protocol_version

    def set_protocol_version(self, version: tuple[int, int, int]) -> None:
        """
        Sets the protocol version for the message.

        Args:
            - version (tuple[int, int, int]):
                The protocol version to set.
        """
        assert isinstance(
            version, tuple
        ), f"Version must be a tuple with a list as the first element. Passed: {version}"
        assert (
            len(version) == 3
        ), f"Version list must contain exactly 3 elements. Passed: {version[0]}"
        self._protocol_version = version

    def get_protocol_version(self) -> tuple:
        """
        Returns the protocol version.

        Returns:
            - tuple:
                The protocol version.
        """
        return self._protocol_version

    @override
    def parse_message(self, message: dict) -> FrostMessage:
        """
        Parses a FrostMessage from a dictionary representation.

        Args:
            - message (dict):
                The dictionary representation of the message.

        Returns:
            - FrostMessage:
                The parsed message.
        """
        return self.build_protocol_register_message(
            target=""
        )  # Placeholder implementation

    @override
    def serialize_message(self, message: FrostMessage) -> dict["str", Any]:
        """
        Serializes a FrostMessage to a dictionary representation.

        Args:
            - message:
                The message to serialize.

        Returns:
            - dict:
                The serialized message.
        """
        temp = {
            "sender": message.sender,
            "target": message.target,
            "identifier": message.identifier,
            "correlation_id": message.correlation_id,
            "header": message.header,
            "payload": message.payload,
        }
        return temp

    def build_read_variable_message(self, target: str, node: str) -> FrostMessage:
        """
        Builds a FrostMessage for reading a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to read.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(node=node),
        )
        return message

    def build_read_variable_response_message(
        self, target: str, node: str, value: Any
    ) -> FrostMessage:
        """
        Builds a FrostMessage as an answer for reading a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node that was read.
            - value (Any):
                The value of the node.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(node=node, value=value),
        )
        return message

    def build_write_variable_message(
        self, target: str, node: str, value: Any
    ) -> FrostMessage:
        """
        Builds a FrostMessage for writing a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to write to.
            - value (Any):
                The value to write.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(node=node, value=value),
        )
        return message

    def build_write_variable_response_message(
        self, target: str, node: str, value: Any
    ) -> FrostMessage:
        """
        Builds a FrostMessage as an answer for writing a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node that was written to.
            - value (Any):
                The value that was written.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(node=node, value=value),
        )
        return message

    def build_subscribe_variable_message(self, target: str, node: str) -> FrostMessage:
        """
        Builds a FrostMessage for subscribing to a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to subscribe to.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=SubscriptionPayload(node=node),
        )
        return message

    def build_subscribe_variable_response_message(
        self, target: str, node: str, value: Any
    ) -> FrostMessage:
        """
        Builds a FrostMessage as a response for subscribing to a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node that was subscribed to.
            - value (Any):
                The current value of the node.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=SubscriptionPayload(node=node, value=value),
        )
        return message

    def build_data_change_subscription_message(
        self, target: str, node: str, deadband: float, is_percent: bool
    ) -> FrostMessage:
        """
        Builds a FrostMessage for a data change subscription.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to subscribe to.
            - deadband (float):
                The deadband for the subscription.
            - is_percent (bool):
                Whether the deadband is a percentage.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=DataChangeSubscriptionPayload(
                node=node, deadband=deadband, is_percent=is_percent
            ),
        )
        return message

    def build_in_range_subscription_message(
        self, target: str, node: str, low: float, high: float
    ) -> FrostMessage:
        """
        Builds a FrostMessage for an in-range subscription.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to subscribe to.
            - low (float):
                The low end of the range.
            - high (float):
                The high end of the range.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=InRangeSubscriptionPayload(node=node, low=low, high=high),
        )
        return message

    def build_out_of_range_subscription_message(
        self, target: str, node: str, low: float, high: float
    ) -> FrostMessage:
        """
        Builds a FrostMessage for an out-of-range subscription.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to subscribe to.
            - low (float):
                The low end of the range.
            - high (float):
                The high end of the range.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=OutOfRangeSubscriptionPayload(node=node, low=low, high=high),
        )
        return message

    def build_unsubscribe_variable_message(
        self, target: str, node: str
    ) -> FrostMessage:
        """
        Builds a FrostMessage for unsubscribing from a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node to unsubscribe from.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.UNSUBSCRIBE,
            ),
            payload=VariablePayload(node=node),
        )
        return message

    def build_unsubscribe_variable_response_message(
        self, target: str, node: str
    ) -> FrostMessage:
        """
        Builds a FrostMessage as a response for unsubscribing from a variable.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node that was unsubscribed from.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.UNSUBSCRIBE,
            ),
            payload=SubscriptionPayload(node=node),
        )
        return message

    def build_method_invoke_message(
        self,
        target: str,
        node: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> FrostMessage:
        """
        Builds a FrostMessage for invoking a method.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The method to invoke.
            - args (list[Any] | None):
                The positional arguments for the method.
            - kwargs (dict[str, Any] | None):
                The keyword arguments for the method.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(
                node=node,
                args=args if args is not None else [],
                kwargs=kwargs if kwargs is not None else {},
            ),
        )
        return message

    def build_method_completed_message(
        self,
        target: str,
        node: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        ret: dict[str, Any] | None = None,
    ) -> FrostMessage:
        """
        Builds a FrostMessage for a method response.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The method that was invoked.
            - args (list[Any] | None):
                The positional arguments for the method.
            - kwargs (dict[str, Any] | None):
                The keyword arguments for the method.
            - ret (dict[str, Any] | None):
                The return value of the method.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.COMPLETED,
            ),
            payload=MethodPayload(
                node=node,
                args=args if args is not None else [],
                kwargs=kwargs if kwargs is not None else {},
                ret=ret if ret is not None else {},
            ),
        )
        return message

    def build_method_started_message(
        self, target: str, node: str, ret: dict[str, Any] | None = None
    ) -> FrostMessage:
        """
        Builds a FrostMessage for a method started notification.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The method that was started.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.STARTED,
            ),
            payload=MethodPayload(node=node, ret=ret if ret is not None else {}),
        )
        return message

    def build_variable_update_message(
        self, target: str, node: str, value: Any
    ) -> FrostMessage:
        """
        Builds a FrostMessage for a variable update notification.

        Args:
            - target (str):
                The target of the message.
            - node (str):
                The node that was updated.
            - value (Any):
                The new value of the node.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.UPDATE,
            ),
            payload=VariablePayload(node=node, value=value),
        )
        return message

    def build_protocol_register_message(self, target: str) -> FrostMessage:
        """
        Builds a FrostMessage for protocol registration.

        Args:
            - target (str):
                The target of the message.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.PROTOCOL,
                msg_name=ProtocolMsgName.REGISTER,
            ),
            payload=ProtocolPayload(node=""),
        )
        return message

    def build_protocol_unregister_message(self, target: str) -> FrostMessage:
        """
        Builds a FrostMessage for protocol unregistration.

        Args:
            - target (str):
                The target of the message.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.PROTOCOL,
                msg_name=ProtocolMsgName.UNREGISTER,
            ),
            payload=ProtocolPayload(node=""),
        )
        return message

    def build_protocol_register_response_message(self, target: str) -> FrostMessage:
        """
        Builds a FrostMessage as a response for protocol registration.

        Args:
            - target (str):
                The target of the message.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.PROTOCOL,
                msg_name=ProtocolMsgName.REGISTER,
            ),
            payload=ProtocolPayload(node=""),
        )
        return message

    def build_protocol_unregister_response_message(self, target: str) -> FrostMessage:
        """
        Builds a FrostMessage as a response for protocol unregistration.

        Args:
            - target (str):
                The target of the message.

        Returns:
            - FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.PROTOCOL,
                msg_name=ProtocolMsgName.UNREGISTER,
            ),
            payload=ProtocolPayload(node=""),
        )
        return message

    def build_error_message(
        self,
        target: str,
        header: FrostHeader,
        error_code: ErrorCode,
        error_message: ErrorMessages,
    ) -> FrostMessage:
        """
        Builds a FrostMessage for an error message.

        Args:
            - target (str):
                The target of the message.
            - header (FrostHeader):
                The header of the original message.
            - error_code (ErrorCode):
                The error code.
            - error_message (ErrorMessages):
                The error message.

        Returns:
            - FrostMessage:
                The built message.
        """
        header.type = MsgType.ERROR
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            header=header,
            payload=ErrorPayload(
                node="", error_code=error_code, error_message=error_message
            ),
        )
        return message
