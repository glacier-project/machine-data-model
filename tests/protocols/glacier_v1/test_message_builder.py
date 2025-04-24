# import uuid
# import pytest
# from machine_data_model.builder.message_builder import GlacierMessageBuilder_v1
# from machine_data_model.protocols.glacier_v1.message import MessageType
# from machine_data_model.protocols.glacier_v1.method_message import MethodCall
# from machine_data_model.protocols.glacier_v1.variable_message import (
#     VariableCall,
#     VarOperation,
# )
#
#
# @pytest.mark.parametrize(
#     "sender, target",
#     [(f"sender_{i}", f"target_{i}") for i in range(3)],
# )
# class TestMessageBuilder:
#     def test_create_variable_message(self, sender: str, target: str) -> None:
#         builder = GlacierMessageBuilder_v1()
#         message = (
#             builder.set_sender(sender)
#             .set_target(target)
#             .set_type(MessageType.REQUEST)
#             .set_variable_payload("varname1", VarOperation.READ, ["arg1", "arg2"])
#             .build()
#         )
#
#         assert message.sender == sender
#         assert message.target == target
#         assert isinstance(message.uuid_code, uuid.UUID)
#         assert message.type == MessageType.REQUEST
#         assert isinstance(message.payload, VariableCall)
#         assert message.payload.varname == "varname1"
#         assert message.payload.operation == VarOperation.READ
#         assert message.payload.args == ["arg1", "arg2"]
#
#     def test_create_method_message(self, sender: str, target: str) -> None:
#         builder = GlacierMessageBuilder_v1()
#         message = (
#             builder.set_sender(sender)
#             .set_target(target)
#             .set_type(MessageType.REQUEST)
#             .set_method_payload("method1", {"param1": "value1", "param2": "value2"})
#             .build()
#         )
#
#         assert message.sender == sender
#         assert message.target == target
#         assert isinstance(message.uuid_code, uuid.UUID)
#         assert message.type == MessageType.REQUEST
#         assert isinstance(message.payload, MethodCall)
#         assert message.payload.method == "method1"
#         assert message.payload.args == {"param1": "value1", "param2": "value2"}
