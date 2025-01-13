import uuid

import pytest

from machine_data_model.builders.message_builder import MessageBuilder
from machine_data_model.protocols.glacier_v1.message import MessageType
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
from machine_data_model.protocols.glacier_v1.variable_message import (
    VariableCall,
    VarOperation,
)


@pytest.mark.parametrize(
    "sender, target",
    [(f"sender_{i}", f"target_{i}") for i in range(3)],
)
class TestMessageBuilder:
    def test_create_variable_message(self, sender: str, target: str) -> None:
        builder = MessageBuilder()
        variable_payload = VariableCall("varname1", VarOperation.READ, ["arg1", "arg2"])
        message = (
            builder.set_sender(sender)
            .set_target(target)
            .set_type(MessageType.REQUEST)
            .set_variable_payload(variable_payload)
            .build()
        )

        assert message.sender == sender
        assert message.target == target
        assert message.payload == variable_payload
        assert message.type == MessageType.REQUEST
        assert isinstance(message.uuid_code, uuid.UUID)

    def test_create_method_message(self, sender: str, target: str) -> None:
        builder = MessageBuilder()
        method_payload = MethodCall("method1", ["arg1", "arg2"])
        message = (
            builder.set_sender(sender)
            .set_target(target)
            .set_type(MessageType.REQUEST)
            .set_method_payload(method_payload)
            .build()
        )

        assert message.sender == sender
        assert message.target == target
        assert message.payload == method_payload
        assert message.type == MessageType.REQUEST
        assert isinstance(message.uuid_code, uuid.UUID)

    @pytest.mark.parametrize(
        "custom_uuid",
        [uuid.uuid4() for _ in range(3)],
    )
    def test_set_uuid_code(
        self, sender: str, target: str, custom_uuid: uuid.UUID
    ) -> None:
        builder = MessageBuilder()
        message = (
            builder.set_sender(sender)
            .set_target(target)
            .set_uuid_code(custom_uuid)
            .set_type(MessageType.ACCEPTED)
            .set_method_payload(MethodCall("method2", ["arg3"]))
            .build()
        )

        assert message.uuid_code == custom_uuid

    def test_set_type(self, sender: str, target: str) -> None:
        builder = MessageBuilder()
        message = (
            builder.set_sender(sender)
            .set_target(target)
            .set_type(MessageType.ACCEPTED)
            .set_method_payload(MethodCall("method3", ["arg4"]))
            .build()
        )

        assert message.type == MessageType.ACCEPTED
