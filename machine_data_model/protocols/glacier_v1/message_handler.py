from machine_data_model.protocols.glacier_v1.message import MessageType
from machine_data_model.protocols.glacier_v1.message import GlacierMessage_v1
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
from machine_data_model.protocols.glacier_v1.variable_message import (
    VariableCall,
    VarOperation,
)
from typing import Any


class MessageHandler:
    message: GlacierMessage_v1

    def set_message(self, mex: GlacierMessage_v1) -> None:
        self.message = mex

    def get_message(self) -> GlacierMessage_v1:
        return self.message

    def has_message(self) -> bool:
        return self.message is not None

    def handle_message(self, node_list: list[Any]) -> list[Any]:
        result: list[Any] = []
        if not self.has_message():
            return result
        type = self.message.type
        if not (type == MessageType.REQUEST):
            return result

        payload = self.message.payload

        if isinstance(payload, VariableCall):
            mex_type: VarOperation = payload.operation
            operation = 0
            varname = payload.varname

            if varname in node_list:
                match mex_type:
                    case VarOperation.READ:
                        operation = VarOperation.READ.value
                    case VarOperation.WRITE:
                        operation = VarOperation.WRITE.value
                    case VarOperation.SUBSCRIBE:
                        operation = VarOperation.SUBSCRIBE.value
                    case VarOperation.UNSUBSCRIBE:
                        operation = VarOperation.UNSUBSCRIBE.value

                result = [operation, varname, payload.args]

        elif isinstance(payload, MethodCall) and payload.method in node_list:
            result = [payload.method, payload.args]

        return result
