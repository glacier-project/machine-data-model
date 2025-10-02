from dataclasses import dataclass, field
import uuid
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MsgNamespace,
    NodeMsgName,
    VariableMsgName,
    MethodMsgName,
    ProtocolMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    FrostPayload,
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


@dataclass(init=True)
class FrostMessageBuilder:
    """
    Builder class for creating Frost protocol messages.
    """

    _protocol_version: tuple = (1, 0, 0)
    _sender: str = ""
    _target: str = ""
    _header: FrostHeader | None = None
    _payload: FrostPayload | None = None
    _identifier: str = ""
    _correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def set_version(self, version: tuple) -> None:
        """Sets the protocol version for the message."""
        self._protocol_version = version

    def _reset(self) -> None:
        """Resets the builder to its initial state."""
        self._sender = ""
        self._target = ""
        self._header = None
        self._payload = None
        self._identifier = ""
        self._correlation_id = ""

    def build(self) -> FrostMessage:
        """
        Constructs a Frost protocol message from the configured parts.
        """
        if not self._header:
            raise ValueError("Header must be set before building a message.")

        message = FrostMessage(
            sender=self._sender,
            target=self._target,
            header=self._header,
            payload=self._payload if self._payload is not None else FrostPayload(),
            identifier=self._identifier
            if self._identifier != ""
            else field(default_factory=lambda: str(uuid.uuid4())),
            correlation_id=self._correlation_id
            if self._correlation_id != ""
            else field(default_factory=lambda: str(uuid.uuid4())),
        )
        self._reset()
        return message

    def with_sender(self, sender: str) -> "FrostMessageBuilder":
        """Sets the sender of the message."""
        self._sender = sender
        return self

    def with_target(self, target: str) -> "FrostMessageBuilder":
        """Sets the target of the message."""
        self._target = target
        return self

    def with_identifier(self, identifier: str) -> "FrostMessageBuilder":
        """Sets the unique identifier of the message."""
        # Note: FrostMessage automatically generates a UUID if none is provided.
        # This method is included for completeness but does not set the identifier directly.
        self._identifier = identifier
        return self

    def with_correlation_id(self, correlation_id: str) -> "FrostMessageBuilder":
        """Sets the correlation ID of the message."""
        # Note: FrostMessage automatically generates a UUID if none is provided.
        # This method is included for completeness but does not set the correlation_id directly.
        self._correlation_id = correlation_id
        return self

    def with_header(self, header: FrostHeader) -> "FrostMessageBuilder":
        """Sets the header of the message."""
        self._header = header
        return self

    def with_payload(self, payload: FrostPayload) -> "FrostMessageBuilder":
        """Sets the payload of the message."""
        self._payload = payload
        return self

    def with_protocol_register_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a protocol register request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.PROTOCOL,
            msg_name=ProtocolMsgName.REGISTER,
        )
        return self

    def with_protocol_register_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a protocol register response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.PROTOCOL,
            msg_name=ProtocolMsgName.REGISTER,
        )
        return self

    def with_protocol_unregister_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a protocol unregister request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.PROTOCOL,
            msg_name=ProtocolMsgName.UNREGISTER,
        )
        return self

    def with_protocol_unregister_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a protocol unregister response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.PROTOCOL,
            msg_name=ProtocolMsgName.UNREGISTER,
        )
        return self

    def with_node_get_info_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get info request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_INFO,
        )
        return self

    def with_node_get_info_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get info response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_INFO,
        )
        return self

    def with_node_get_children_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get children request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_CHILDREN,
        )
        return self

    def with_node_get_children_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get children response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_CHILDREN,
        )
        return self

    def with_node_get_variables_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get variables request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_VARIABLES,
        )
        return self

    def with_node_get_variables_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get variables response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_VARIABLES,
        )
        return self

    def with_node_get_methods_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get methods request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_METHODS,
        )
        return self

    def with_node_get_methods_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a node get methods response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.NODE,
            msg_name=NodeMsgName.GET_METHODS,
        )
        return self

    def with_variable_read_value_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable read value request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        )
        return self

    def with_variable_read_value_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable read value response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        )
        return self

    def with_variable_write_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable set value request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.WRITE,
        )
        return self

    def with_variable_write_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable set value response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.WRITE,
        )
        return self

    def with_variable_subscribe_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable subscribe request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.SUBSCRIBE,
        )
        return self

    def with_variable_subscribe_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable subscribe response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.SUBSCRIBE,
        )
        return self

    def with_variable_unsubscribe_request_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable unsubscribe request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.UNSUBSCRIBE,
        )
        return self

    def with_variable_unsubscribe_response_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable unsubscribe response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.UNSUBSCRIBE,
        )
        return self

    def with_variable_update_header(self) -> "FrostMessageBuilder":
        """Sets the header for a variable update notification."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.UPDATE,
        )
        return self

    def with_method_invoke_header(self) -> "FrostMessageBuilder":
        """Sets the header for a method invoke request."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.REQUEST,
            namespace=MsgNamespace.METHOD,
            msg_name=MethodMsgName.INVOKE,
        )
        return self

    def with_method_started_header(self) -> "FrostMessageBuilder":
        """Sets the header for a method started response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.METHOD,
            msg_name=MethodMsgName.STARTED,
        )
        return self

    def with_method_completed_header(self) -> "FrostMessageBuilder":
        """Sets the header for a method completed response."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.RESPONSE,
            namespace=MsgNamespace.METHOD,
            msg_name=MethodMsgName.COMPLETED,
        )
        return self

    def with_error_header(
        self,
        namespace: MsgNamespace,
        msg_name: NodeMsgName | VariableMsgName | MethodMsgName | ProtocolMsgName,
    ) -> "FrostMessageBuilder":
        """Sets the header for an error message."""
        self._header = FrostHeader(
            version=self._protocol_version,
            type=MsgType.ERROR,
            namespace=namespace,
            msg_name=msg_name,
        )
        return self

    def with_protocol_payload(self) -> "FrostMessageBuilder":
        """Sets the payload for a protocol message."""
        self._payload = ProtocolPayload(node="")
        return self

    def with_variable_payload(
        self, node: str, value: Any | None = None
    ) -> "FrostMessageBuilder":
        """Sets the payload for a variable message."""
        self._payload = VariablePayload(node=node, value=value)
        return self

    def with_subscription_payload(self, node: str) -> "FrostMessageBuilder":
        """Sets the payload for a subscription message."""
        self._payload = SubscriptionPayload(node=node)
        return self

    def with_data_change_subscription_payload(
        self, node: str, deadband: float, is_percent: bool
    ) -> "FrostMessageBuilder":
        """Sets the payload for a data change subscription message."""
        self._payload = DataChangeSubscriptionPayload(
            node=node, deadband=deadband, is_percent=is_percent
        )
        return self

    def with_in_range_subscription_payload(
        self, node: str, low: float, high: float
    ) -> "FrostMessageBuilder":
        """Sets the payload for an in-range subscription message."""
        self._payload = InRangeSubscriptionPayload(node=node, low=low, high=high)
        return self

    def with_out_of_range_subscription_payload(
        self, node: str, low: float, high: float
    ) -> "FrostMessageBuilder":
        """Sets the payload for an out-of-range subscription message."""
        self._payload = OutOfRangeSubscriptionPayload(node=node, low=low, high=high)
        return self

    def with_method_payload(
        self,
        node: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        ret: dict[str, Any] | None = None,
    ) -> "FrostMessageBuilder":
        """Sets the payload for a method message."""
        self._payload = MethodPayload(
            node=node,
            args=args if args is not None else [],
            kwargs=kwargs if kwargs is not None else {},
            ret=ret if ret is not None else {},
        )
        return self

    def with_error_payload(
        self, node: str, error_code: ErrorCode, error_message: ErrorMessages
    ) -> "FrostMessageBuilder":
        """Sets the payload for an error message."""
        self._payload = ErrorPayload(
            node=node, error_code=error_code, error_message=error_message
        )
        return self
