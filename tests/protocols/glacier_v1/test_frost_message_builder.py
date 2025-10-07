import uuid

import pytest
from machine_data_model.protocols.frost_v1.frost_header import (
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
    ProtocolMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    SubscriptionPayload,
    VariablePayload,
    MethodPayload,
    ErrorPayload,
)
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    NodeMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    DataChangeSubscriptionPayload,
    InRangeSubscriptionPayload,
    OutOfRangeSubscriptionPayload,
    ProtocolPayload,
    ErrorCode,
    ErrorMessages,
)


@pytest.fixture
def builder() -> FrostMessageBuilder:
    """Provides a fresh FrostMessageBuilder instance for each test."""
    return FrostMessageBuilder()


def test_build_no_header_raises_error(builder: FrostMessageBuilder) -> None:
    """Test that building a message without a header raises a ValueError."""
    with pytest.raises(
        ValueError, match="Header must be set before building a message."
    ):
        builder.build()


def test_build_resets_builder(builder: FrostMessageBuilder) -> None:
    """Test that the builder is reset after a message is built."""
    builder.with_sender("test_sender").with_protocol_register_request_header()
    assert builder._sender == "test_sender"
    assert builder._header is not None

    builder.build()

    assert builder._sender == ""
    assert builder._header is None


def test_with_sender_target_id_correlation_id(builder: FrostMessageBuilder) -> None:
    """Test setting sender, target, identifier, and correlation_id."""
    sender = "sender_id"
    target = "target_id"
    identifier = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    message = (
        builder.with_sender(sender)
        .with_target(target)
        .with_identifier(identifier)
        .with_correlation_id(correlation_id)
        .with_protocol_register_request_header()
        .build()
    )

    assert isinstance(message, FrostMessage)
    assert message.sender == sender
    assert message.target == target
    assert message.identifier == identifier
    assert message.correlation_id == correlation_id


def test_set_version(builder: FrostMessageBuilder) -> None:
    """Test setting a custom protocol version."""
    custom_version = (2, 1, 0)
    builder.set_version(custom_version)
    message = builder.with_protocol_register_request_header().build()
    assert message.header.version == custom_version


@pytest.mark.parametrize(
    "header_method_name, expected_type, expected_namespace, expected_msg_name",
    [
        (
            "with_protocol_register_request_header",
            MsgType.REQUEST,
            MsgNamespace.PROTOCOL,
            ProtocolMsgName.REGISTER,
        ),
        (
            "with_protocol_register_response_header",
            MsgType.RESPONSE,
            MsgNamespace.PROTOCOL,
            ProtocolMsgName.REGISTER,
        ),
        (
            "with_protocol_unregister_request_header",
            MsgType.REQUEST,
            MsgNamespace.PROTOCOL,
            ProtocolMsgName.UNREGISTER,
        ),
        (
            "with_protocol_unregister_response_header",
            MsgType.RESPONSE,
            MsgNamespace.PROTOCOL,
            ProtocolMsgName.UNREGISTER,
        ),
        (
            "with_node_get_info_request_header",
            MsgType.REQUEST,
            MsgNamespace.NODE,
            NodeMsgName.GET_INFO,
        ),
        (
            "with_node_get_info_response_header",
            MsgType.RESPONSE,
            MsgNamespace.NODE,
            NodeMsgName.GET_INFO,
        ),
        (
            "with_node_get_children_request_header",
            MsgType.REQUEST,
            MsgNamespace.NODE,
            NodeMsgName.GET_CHILDREN,
        ),
        (
            "with_node_get_children_response_header",
            MsgType.RESPONSE,
            MsgNamespace.NODE,
            NodeMsgName.GET_CHILDREN,
        ),
        (
            "with_node_get_variables_request_header",
            MsgType.REQUEST,
            MsgNamespace.NODE,
            NodeMsgName.GET_VARIABLES,
        ),
        (
            "with_node_get_variables_response_header",
            MsgType.RESPONSE,
            MsgNamespace.NODE,
            NodeMsgName.GET_VARIABLES,
        ),
        (
            "with_node_get_methods_request_header",
            MsgType.REQUEST,
            MsgNamespace.NODE,
            NodeMsgName.GET_METHODS,
        ),
        (
            "with_node_get_methods_response_header",
            MsgType.RESPONSE,
            MsgNamespace.NODE,
            NodeMsgName.GET_METHODS,
        ),
        (
            "with_variable_read_value_request_header",
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.READ,
        ),
        (
            "with_variable_read_value_response_header",
            MsgType.RESPONSE,
            MsgNamespace.VARIABLE,
            VariableMsgName.READ,
        ),
        (
            "with_variable_write_request_header",
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.WRITE,
        ),
        (
            "with_variable_write_response_header",
            MsgType.RESPONSE,
            MsgNamespace.VARIABLE,
            VariableMsgName.WRITE,
        ),
        (
            "with_variable_subscribe_request_header",
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.SUBSCRIBE,
        ),
        (
            "with_variable_subscribe_response_header",
            MsgType.RESPONSE,
            MsgNamespace.VARIABLE,
            VariableMsgName.SUBSCRIBE,
        ),
        (
            "with_variable_unsubscribe_request_header",
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.UNSUBSCRIBE,
        ),
        (
            "with_variable_unsubscribe_response_header",
            MsgType.RESPONSE,
            MsgNamespace.VARIABLE,
            VariableMsgName.UNSUBSCRIBE,
        ),
        (
            "with_variable_update_header",
            MsgType.RESPONSE,
            MsgNamespace.VARIABLE,
            VariableMsgName.UPDATE,
        ),
        (
            "with_method_invoke_header",
            MsgType.REQUEST,
            MsgNamespace.METHOD,
            MethodMsgName.INVOKE,
        ),
        (
            "with_method_started_header",
            MsgType.RESPONSE,
            MsgNamespace.METHOD,
            MethodMsgName.STARTED,
        ),
        (
            "with_method_completed_header",
            MsgType.RESPONSE,
            MsgNamespace.METHOD,
            MethodMsgName.COMPLETED,
        ),
    ],
)
def test_header_methods(
    builder: FrostMessageBuilder,
    header_method_name: str,
    expected_type: MsgType,
    expected_namespace: MsgNamespace,
    expected_msg_name: ProtocolMsgName | NodeMsgName | VariableMsgName | MethodMsgName,
) -> None:
    """Test all header helper methods."""
    header_method = getattr(builder, header_method_name)
    message = header_method().build()
    assert isinstance(message.header, FrostHeader)
    assert message.header.type == expected_type
    assert message.header.namespace == expected_namespace
    assert message.header.msg_name == expected_msg_name


def test_with_error_header(builder: FrostMessageBuilder) -> None:
    """Test the error header helper method."""
    message = builder.with_error_header(
        MsgNamespace.VARIABLE, VariableMsgName.READ
    ).build()
    assert message.header.type == MsgType.ERROR
    assert message.header.namespace == MsgNamespace.VARIABLE
    assert message.header.msg_name == VariableMsgName.READ


def test_with_protocol_payload(builder: FrostMessageBuilder) -> None:
    """Test the protocol payload helper method."""
    message = (
        builder.with_protocol_register_request_header().with_protocol_payload().build()
    )
    assert isinstance(message.payload, ProtocolPayload)


def test_with_variable_payload(builder: FrostMessageBuilder) -> None:
    """Test the variable payload helper method."""
    node, value = "some.node", 123.45
    message = (
        builder.with_variable_read_value_response_header()
        .with_variable_payload(node=node, value=value)
        .build()
    )
    assert isinstance(message.payload, VariablePayload)
    assert message.payload.node == node
    assert message.payload.value == value


def test_with_subscription_payload(builder: FrostMessageBuilder) -> None:
    """Test the subscription payload helper method."""
    node = "some.node"
    message = (
        builder.with_variable_unsubscribe_request_header()
        .with_subscription_payload(node=node)
        .build()
    )
    assert isinstance(message.payload, SubscriptionPayload)
    assert message.payload.node == node


def test_with_data_change_subscription_payload(builder: FrostMessageBuilder) -> None:
    """Test the data change subscription payload helper method."""
    node, deadband, is_percent = "some.node", 5.0, True
    message = (
        builder.with_variable_subscribe_request_header()
        .with_data_change_subscription_payload(
            node=node, deadband=deadband, is_percent=is_percent
        )
        .build()
    )
    assert isinstance(message.payload, DataChangeSubscriptionPayload)
    assert message.payload.node == node
    assert message.payload.deadband == deadband
    assert message.payload.is_percent == is_percent


def test_with_in_range_subscription_payload(builder: FrostMessageBuilder) -> None:
    """Test the in-range subscription payload helper method."""
    node, low, high = "some.node", 10.0, 20.0
    message = (
        builder.with_variable_subscribe_request_header()
        .with_in_range_subscription_payload(node=node, low=low, high=high)
        .build()
    )
    assert isinstance(message.payload, InRangeSubscriptionPayload)
    assert message.payload.node == node
    assert message.payload.low == low
    assert message.payload.high == high


def test_with_out_of_range_subscription_payload(builder: FrostMessageBuilder) -> None:
    """Test the out-of-range subscription payload helper method."""
    node, low, high = "some.node", 10.0, 20.0
    message = (
        builder.with_variable_subscribe_request_header()
        .with_out_of_range_subscription_payload(node=node, low=low, high=high)
        .build()
    )
    assert isinstance(message.payload, OutOfRangeSubscriptionPayload)
    assert message.payload.node == node
    assert message.payload.low == low
    assert message.payload.high == high


def test_with_method_payload(builder: FrostMessageBuilder) -> None:
    """Test the method payload helper method."""
    node, args, kwargs, ret = "some.method", [1, "a"], {"b": 2}, {"c": 3}
    message = (
        builder.with_method_invoke_header()
        .with_method_payload(node=node, args=args, kwargs=kwargs, ret=ret)
        .build()
    )
    assert isinstance(message.payload, MethodPayload)
    assert message.payload.node == node
    assert message.payload.args == args
    assert message.payload.kwargs == kwargs
    assert message.payload.ret == ret


def test_with_error_payload(builder: FrostMessageBuilder) -> None:
    """Test the error payload helper method."""
    node, code, msg = "some.node", ErrorCode.BAD_REQUEST, ErrorMessages.BAD_REQUEST
    message = (
        builder.with_error_header(MsgNamespace.NODE, NodeMsgName.GET_INFO)
        .with_error_payload(node=node, error_code=code, error_message=msg)
        .build()
    )
    assert isinstance(message.payload, ErrorPayload)
    assert message.payload.node == node
    assert message.payload.error_code == code
    assert message.payload.error_message == msg
