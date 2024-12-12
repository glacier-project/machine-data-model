from machine_data_model.protocols.glacier_v1.message import (
    Message,
    MessageTopology,
    VarOperation,
    VariableCall,
    MethodCall
)
import uuid

def create_variable_message(sender: str, target: str, varname: str, operation: VarOperation, args: list) -> Message:
    payload = VariableCall(varname, operation, args)
    return Message(
        sender=sender,
        target=target,
        uuid_code=uuid.uuid4(),
        topology=MessageTopology.REQUEST,
        payload=payload
    )

def create_method_message(sender: str, target: str, method: str, args: list) -> Message:
    payload = MethodCall(method, args)
    return Message(
        sender=sender,
        target=target,
        uuid_code=uuid.uuid4(),
        topology=MessageTopology.REQUEST,
        payload=payload
    )