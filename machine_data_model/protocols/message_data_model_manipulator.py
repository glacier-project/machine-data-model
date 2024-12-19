from machine_data_model.protocols.glacier_v1.enumeration_for_messages import (
    MessageType
)
from machine_data_model.protocols.glacier_v1.message import Message
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
from machine_data_model.protocols.glacier_v1.variable_message import (
    VariableCall,
    VarOperation,
)


def handle_message(message: Message, variable_list: list) -> list:
    topology = message.topology
    sem = False
    if topology == MessageType.REQUEST:
        sem = True
    payload = message.payload
    result = None

    if isinstance(payload, VariableCall) and sem:
        type = payload.operation
        operation = 0
        varname = payload.varname
        if varname in variable_list:
            match type:
                case VarOperation.READ:
                    operation = VarOperation.READ.value
                case VarOperation.WRITE:
                    operation = VarOperation.WRITE.value
                case VarOperation.SUBSCRIBE:
                    operation = VarOperation.SUBSCRIBE.value
                case VarOperation.UNSUBSCRIBE:
                    operation = VarOperation.UNSUBSCRIBE.value

            args = payload.args
            result = [operation, varname, args]

    elif isinstance(payload, MethodCall) and sem:
        name = payload.method
        args = payload.args
        result = [name, args]

    if result is None:
        return []
    else:
        return result
