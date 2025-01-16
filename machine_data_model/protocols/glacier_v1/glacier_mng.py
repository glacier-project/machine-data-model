from typing_extensions import override

from machine_data_model.data_model import DataModel
from machine_data_model.protocols.protocol_mng import ProtocolMng, Message
from machine_data_model.protocols.glacier_v1.message import (
    GlacierMessage_v1,
    MessageType,
)
from machine_data_model.protocols.glacier_v1.variable_message import (
    VariableCall,
    VarOperation,
)
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
import uuid


class GlacierMng(ProtocolMng):
    """
    This class is responsible for handling messages encoded with the Glacier protocol
    and updating the machine data model accordingly.
    """

    def __init__(self, data_model: DataModel):
        super().__init__(data_model)

    @override
    def handle_message(self, msg: Message) -> Message:
        if isinstance(msg, GlacierMessage_v1):
            payload = msg.payload

            if isinstance(payload, VariableCall):
                operation: VarOperation = payload.operation
                varname = payload.varname
                match operation:
                    case VarOperation.READ:
                        value = self._data_model.read_variable(varname)
                        response = GlacierMessage_v1(
                            sender=msg.target,
                            target=msg.sender,
                            uuid_code=uuid.uuid4(),
                            type=MessageType.SUCCESS,
                            payload=VariableCall(
                                varname, VarOperation.READ, args=value
                            ),
                        )
                        return response

                    case VarOperation.WRITE:
                        value = payload.args
                        self._data_model.write_variable(varname, value)
                        response = GlacierMessage_v1(
                            sender=msg.target,
                            target=msg.sender,
                            uuid_code=uuid.uuid4(),
                            type=MessageType.SUCCESS,
                            payload=VariableCall(
                                varname, VarOperation.WRITE, args=value
                            ),
                        )
                        return response

                    # case VarOperation.SUBSCRIBE:
                    #     self.data_model.subscribe_variable(varname)
                    #     response = GlacierMessage_v1(VariableCall(varname, VarOperation.SUBSCRIBE))
                    #     return response

                    case _:
                        raise ValueError(f"Unsupported operation: {operation}")

            elif isinstance(payload, MethodCall):
                # TODO implement method call handling
                return msg

        else:
            raise ValueError("Message is not of type GlacierMessage_v1")
        return msg

    """
    @override
    def parse_message(self, raw_msg: str) -> MessageGlacier_v1:
        return None

    @override
    def create_response(self, msg: MessageGlacier_v1) -> MessageGlacier_v1:
        return msg

    @override
    def read_request(self, msg: MessageGlacier_v1) -> MessageGlacier_v1:
        return msg

    @override
    def write_request(self, msg: MessageGlacier_v1) -> MessageGlacier_v1:
        return msg

    @override
    def subscribe_request(self, msg: MessageGlacier_v1) -> MessageGlacier_v1:
        return msg

    @override
    def method_call_request(self, msg: MessageGlacier_v1) -> MessageGlacier_v1:
        return msg"""
