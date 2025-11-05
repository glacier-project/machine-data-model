import pytest
import random
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
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from tests import NUM_TESTS, gen_random_string

sender = "test_sender"


@pytest.fixture
def message_builder() -> FrostMessageBuilder:
    return FrostMessageBuilder(sender=sender, protocol_version=(1, 0, 0))


class TestFrostMessageBuilder:
    def test_version(
        self,
        message_builder: FrostMessageBuilder,
    ) -> None:
        assert message_builder.get_protocol_version() == (1, 0, 0)
        new_version = (2, 1, 0)
        message_builder.set_protocol_version(new_version)
        assert message_builder.get_protocol_version() == new_version

    @pytest.mark.parametrize(
        "target, node",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_read_variable_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
    ) -> None:
        message = message_builder.build_read_variable_message(target=target, node=node)
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.READ
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.value is None
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node, value",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_response_read_variable_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        value: float,
    ) -> None:
        message = message_builder.build_read_variable_response_message(
            target=target, node=node, value=value
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.READ
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.value == value
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node, value",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_write_variable_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        value: float,
    ) -> None:
        message = message_builder.build_write_variable_message(
            target=target, node=node, value=value
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.WRITE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.value == value
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node, value",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_response_write_variable_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        value: float,
    ) -> None:
        message = message_builder.build_write_variable_response_message(
            target=target, node=node, value=value
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.WRITE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.value == value
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_subscribe_variable_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
    ) -> None:
        message = message_builder.build_subscribe_variable_message(
            target=target, node=node
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.SUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, SubscriptionPayload)
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node, value",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_subscribe_variable_response_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        value: float,
    ) -> None:
        message = message_builder.build_subscribe_variable_response_message(
            target=target, node=node, value=value
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.SUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, SubscriptionPayload)
        assert message.payload.node == node
        assert message.payload.value == value

    @pytest.mark.parametrize(
        "target, node, deadband, is_percent",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 1),
                random.choice([True, False]),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_data_change_subscription_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        deadband: float,
        is_percent: bool,
    ) -> None:
        message = message_builder.build_data_change_subscription_message(
            target=target, node=node, deadband=deadband, is_percent=is_percent
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.SUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, DataChangeSubscriptionPayload)
        assert message.payload.node == node
        assert message.payload.deadband == deadband
        assert message.payload.is_percent == is_percent

    @pytest.mark.parametrize(
        "target, node, low, high",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 50),
                random.uniform(50, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_in_range_subscription_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        low: float,
        high: float,
    ) -> None:
        message = message_builder.build_in_range_subscription_message(
            target=target, node=node, low=low, high=high
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.SUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, InRangeSubscriptionPayload)
        assert message.payload.node == node
        assert message.payload.low == low
        assert message.payload.high == high

    @pytest.mark.parametrize(
        "target, node, low, high",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 50),
                random.uniform(50, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_out_of_range_subscription_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        low: float,
        high: float,
    ) -> None:
        message = message_builder.build_out_of_range_subscription_message(
            target=target, node=node, low=low, high=high
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.SUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, OutOfRangeSubscriptionPayload)
        assert message.payload.node == node
        assert message.payload.low == low
        assert message.payload.high == high

    @pytest.mark.parametrize(
        "target, node",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_unsubscribe_variable_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
    ) -> None:
        message = message_builder.build_unsubscribe_variable_message(
            target=target, node=node
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.UNSUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_unsubscribe_variable_response_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
    ) -> None:
        message = message_builder.build_unsubscribe_variable_response_message(
            target=target, node=node
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.UNSUBSCRIBE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node, args, kwargs",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                [random.randint(0, 100), gen_random_string(5)],
                {"kwarg1": random.uniform(0, 1), "kwarg2": True},
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_method_invoke_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        args: list,
        kwargs: dict,
    ) -> None:
        message = message_builder.build_method_invoke_message(
            target=target, node=node, args=args, kwargs=kwargs
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.METHOD
        assert message.header.msg_name == MethodMsgName.INVOKE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, MethodPayload)
        assert message.payload.node == node
        assert message.payload.args == args
        assert message.payload.kwargs == kwargs

    @pytest.mark.parametrize(
        "target, node, args, kwargs, ret",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                [random.randint(0, 100), gen_random_string(5)],
                {"kwarg1": random.uniform(0, 1), "kwarg2": True},
                {"ret1": "value", "ret2": 123},
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_method_completed_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        args: list,
        kwargs: dict,
        ret: dict,
    ) -> None:
        message = message_builder.build_method_completed_message(
            target=target, node=node, args=args, kwargs=kwargs, ret=ret
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.METHOD
        assert message.header.msg_name == MethodMsgName.COMPLETED
        assert message.header.timestamp is not None
        assert isinstance(message.payload, MethodPayload)
        assert message.payload.node == node
        assert message.payload.args == args
        assert message.payload.kwargs == kwargs
        assert message.payload.ret == ret

    @pytest.mark.parametrize(
        "target, node",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_method_started_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
    ) -> None:
        message = message_builder.build_method_started_message(target=target, node=node)
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.METHOD
        assert message.header.msg_name == MethodMsgName.STARTED
        assert message.header.timestamp is not None
        assert isinstance(message.payload, MethodPayload)
        assert message.payload.node == node

    @pytest.mark.parametrize(
        "target, node, value",
        [
            (
                gen_random_string(10),
                gen_random_string(15),
                random.uniform(0, 100),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_variable_update_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        node: str,
        value: float,
    ) -> None:
        message = message_builder.build_variable_update_message(
            target=target, node=node, value=value
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.VARIABLE
        assert message.header.msg_name == VariableMsgName.UPDATE
        assert message.header.timestamp is not None
        assert isinstance(message.payload, VariablePayload)
        assert message.payload.node == node
        assert message.payload.value == value

    @pytest.mark.parametrize(
        "target",
        [(gen_random_string(10),) for _ in range(NUM_TESTS)],
    )
    def test_build_protocol_register_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
    ) -> None:
        message = message_builder.build_protocol_register_message(target=target)
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.PROTOCOL
        assert message.header.msg_name == ProtocolMsgName.REGISTER
        assert message.header.timestamp is not None
        assert isinstance(message.payload, ProtocolPayload)

    @pytest.mark.parametrize(
        "target",
        [(gen_random_string(10),) for _ in range(NUM_TESTS)],
    )
    def test_build_protocol_unregister_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
    ) -> None:
        message = message_builder.build_protocol_unregister_message(target=target)
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.REQUEST
        assert message.header.namespace == MsgNamespace.PROTOCOL
        assert message.header.msg_name == ProtocolMsgName.UNREGISTER
        assert message.header.timestamp is not None
        assert isinstance(message.payload, ProtocolPayload)

    @pytest.mark.parametrize(
        "target",
        [(gen_random_string(10),) for _ in range(NUM_TESTS)],
    )
    def test_build_protocol_register_response_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
    ) -> None:
        message = message_builder.build_protocol_register_response_message(
            target=target
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.PROTOCOL
        assert message.header.msg_name == ProtocolMsgName.REGISTER
        assert message.header.timestamp is not None
        assert isinstance(message.payload, ProtocolPayload)

    @pytest.mark.parametrize(
        "target",
        [(gen_random_string(10),) for _ in range(NUM_TESTS)],
    )
    def test_build_protocol_unregister_response_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
    ) -> None:
        message = message_builder.build_protocol_unregister_response_message(
            target=target
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.RESPONSE
        assert message.header.namespace == MsgNamespace.PROTOCOL
        assert message.header.msg_name == ProtocolMsgName.UNREGISTER
        assert message.header.timestamp is not None
        assert isinstance(message.payload, ProtocolPayload)

    @pytest.mark.parametrize(
        "target, error_code, error_message",
        [
            (
                gen_random_string(10),
                random.choice(list(ErrorCode)),
                random.choice(list(ErrorMessages)),
            )
            for _ in range(NUM_TESTS)
        ],
    )
    def test_build_error_message(
        self,
        message_builder: FrostMessageBuilder,
        target: str,
        error_code: ErrorCode,
        error_message: ErrorMessages,
    ) -> None:
        header = FrostHeader(
            version=message_builder.get_protocol_version(),
            type=MsgType.REQUEST,
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        )
        message = message_builder.build_error_message(
            target=target,
            header=header,
            error_code=error_code,
            error_message=error_message,
        )
        assert message.sender == sender
        assert message.target == target
        assert message.header.version == message_builder.get_protocol_version()
        assert message.header.type == MsgType.ERROR
        assert message.header.timestamp is not None
        assert isinstance(message.payload, ErrorPayload)
        assert message.payload.error_code == error_code
        assert message.payload.error_message == error_message
