from typing import Any
import uuid

from typing_extensions import override

from machine_data_model.protocols.frost_v1 import FROST_PROTOCOL_VERSION
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MethodMsgName,
    MsgNamespace,
    MsgType,
    ProtocolMsgName,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    DataChangeSubscriptionPayload,
    ErrorCode,
    ErrorMessages,
    ErrorPayload,
    InRangeSubscriptionPayload,
    MethodPayload,
    OutOfRangeSubscriptionPayload,
    ProtocolPayload,
    SubscriptionPayload,
    VariablePayload,
)
from machine_data_model.protocols.message_builder import MessageBuilder


class FrostMessageBuilder(MessageBuilder):
    """Builder class for creating Frost protocol messages.

    This class extends the abstract MessageBuilder and provides concrete
    implementations for building Frost protocol-specific messages.

    Attributes:
        _protocol_version (tuple[int, int, int]):
            The Frost protocol version as (major, minor, patch).

    """

    def __init__(
        self,
        sender: str,
        protocol_version: tuple[int, int, int] | None = None,
    ):
        """Initialize the FrostMessageBuilder.

        Args:
            sender (str):
                The sender identifier for messages created by this builder.
            protocol_version (tuple[int, int, int] | None):
                The Frost protocol version as (major, minor, patch).
                If None, defaults to the latest version defined in
                FROST_PROTOCOL_VERSION.
        """
        super().__init__(sender)
        self._protocol_version = (
            protocol_version
            if protocol_version is not None
            else FROST_PROTOCOL_VERSION
        )

    def get_protocol_version(self) -> tuple[int, int, int]:
        """Get the Frost protocol version.

        Returns:
            tuple[int, int, int]:
                The Frost protocol version as (major, minor, patch).
        """
        return self._protocol_version

    def set_protocol_version(
        self, protocol_version: tuple[int, int, int]
    ) -> None:
        """Set the Frost protocol version.

        Args:
            protocol_version (tuple[int, int, int]):
                The Frost protocol version as (major, minor, patch).

        Returns:
            None
        """
        assert (
            len(protocol_version) == 3
        ), "Protocol version must be a tuple of (major, minor, patch)."
        assert all(
            isinstance(v, int) and v >= 0 for v in protocol_version
        ), "Protocol version values must be non-negative integers."
        self._protocol_version = protocol_version

    @override
    def build_read_variable_message(
        self, target: str, node: str, correlation_id: str | None = None
    ) -> FrostMessage:
        """Build a FrostMessage for reading a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to read.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage as an answer for reading a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node that was read.
            value (Any):
                The value of the node.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(node=node, value=value),
        )
        return message

    @override
    def build_write_variable_message(
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for writing a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to write to.
            value (Any):
                The value to write.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage as an answer for writing a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node that was written to.
            value (Any):
                The value that was written.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(node=node, value=value),
        )
        return message

    def build_subscribe_variable_message(
        self, target: str, node: str, correlation_id: str | None = None
    ) -> FrostMessage:
        """Build a FrostMessage for subscribing to a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to subscribe to.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage as a response for subscribing to a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node that was subscribed to.
            value (Any):
                The current value of the node.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        deadband: float,
        is_percent: bool,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for a data change subscription.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to subscribe to.
            deadband (float):
                The deadband for the subscription.
            is_percent (bool):
                Whether the deadband is a percentage.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        low: float,
        high: float,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for an in-range subscription.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to subscribe to.
            low (float):
                The low end of the range.
            high (float):
                The high end of the range.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        low: float,
        high: float,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for an out-of-range subscription.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to subscribe to.
            low (float):
                The low end of the range.
            high (float):
                The high end of the range.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=OutOfRangeSubscriptionPayload(
                node=node, low=low, high=high
            ),
        )
        return message

    def build_unsubscribe_variable_message(
        self, target: str, node: str, correlation_id: str | None = None
    ) -> FrostMessage:
        """Build a FrostMessage for unsubscribing from a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node to unsubscribe from.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self, target: str, node: str, correlation_id: str | None = None
    ) -> FrostMessage:
        """Build a FrostMessage as a response for unsubscribing from a variable.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node that was unsubscribed from.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.UNSUBSCRIBE,
            ),
            payload=SubscriptionPayload(node=node),
        )
        return message

    @override
    def build_invoke_method_message(
        self,
        target: str,
        node: str,
        correlation_id: str | None = None,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for invoking a method.

        Args:
            target (str):
                The target of the message.
            node (str):
                The method to invoke.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.
            args (list[Any] | None):
                The positional arguments for the method.
            kwargs (dict[str, Any] | None):
                The keyword arguments for the method.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for a method response.

        Args:
            target (str):
                The target of the message.
            node (str):
                The method that was invoked.
            args (list[Any] | None):
                The positional arguments for the method.
            kwargs (dict[str, Any] | None):
                The keyword arguments for the method.
            ret (dict[str, Any] | None):
                The return value of the method.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        self,
        target: str,
        node: str,
        ret: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for a method started notification.

        Args:
            target (str):
                The target of the message.
            node (str):
                The method that was started.
            ret (dict[str, Any] | None):
                The initial return values. Defaults to None.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.STARTED,
            ),
            payload=MethodPayload(
                node=node, ret=ret if ret is not None else {}
            ),
        )
        return message

    def build_variable_update_message(
        self,
        target: str,
        node: str,
        value: Any,
        correlation_id: str | None = None,
    ) -> FrostMessage:
        """Build a FrostMessage for a variable update notification.

        Args:
            target (str):
                The target of the message.
            node (str):
                The node that was updated.
            value (Any):
                The new value of the node.
            correlation_id (str | None):
                The correlation ID for the message. Defaults to None.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        """Build a FrostMessage for protocol registration.

        Args:
            target (str):
                The target of the message.

        Returns:
            FrostMessage:
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
        """Build a FrostMessage for protocol unregistration.

        Args:
            target (str):
                The target of the message.

        Returns:
            FrostMessage:
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

    def build_protocol_register_response_message(
        self, target: str, correlation_id: str | None = None
    ) -> FrostMessage:
        """Build a FrostMessage as a response for protocol registration.

        Args:
            target (str):
                The target of the message.
            correlation_id (str | None):
                The correlation ID of the original message.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.PROTOCOL,
                msg_name=ProtocolMsgName.REGISTER,
            ),
            payload=ProtocolPayload(node=""),
        )
        return message

    def build_protocol_unregister_response_message(
        self, target: str, correlation_id: str | None = None
    ) -> FrostMessage:
        """Build a FrostMessage as a response for protocol unregistration.

        Args:
            target (str):
                The target of the message.
            correlation_id (str | None):
                The correlation ID of the original message.

        Returns:
            FrostMessage:
                The built message.
        """
        message = FrostMessage(
            sender=self._sender,
            target=target,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if correlation_id is None
            else correlation_id,
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
        message: FrostMessage,
        error_code: ErrorCode,
        error_message: ErrorMessages,
    ) -> FrostMessage:
        """Build a FrostMessage for an error message.

        Args:
            message (FrostMessage):
                The original message that caused the error.
            error_code (ErrorCode):
                The error code.
            error_message (ErrorMessages):
                The error message.

        Returns:
            FrostMessage:
                The built message.
        """
        new_msg = FrostMessage(
            sender=self._sender,
            target=message.sender,
            identifier=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
            if message.correlation_id is None or ""
            else message.correlation_id,
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.ERROR,
                namespace=message.header.namespace,
                msg_name=message.header.msg_name,
            ),
            payload=ErrorPayload(
                node="", error_code=error_code, error_message=error_message
            ),
        )
        return new_msg
