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


class GlacierProtocolMng(ProtocolMng):
    """
    This class is responsible for handling messages encoded with the Glacier protocol
    and updating the machine data model accordingly.
    """

    def __init__(self, data_model: DataModel):
        super().__init__(data_model)

    @override
    def handle_message(self, msg: Message) -> Message:
        """
        This method handles a message encoded with the Glacier protocol and updates the
        machine data model accordingly.
        :param msg: The message to be handled.
        :return: A response message.
        """
        if isinstance(msg, GlacierMessage_v1):
            payload = msg.payload

            if isinstance(payload, VariableCall):
                operation: VarOperation = payload.operation
                match operation:
                    case VarOperation.READ:
                        return self.read_request(msg)

                    case VarOperation.WRITE:
                        return self.write_request(msg)

                    # TODO: Implement these cases
                    # case VarOperation.SUBSCRIBE:
                    #     return self.subscribe_request(msg)

                    # case VarOperation.UNSUBSCRIBE:
                    #     return self.unsubscribe_request(msg)

                    case _:
                        raise ValueError(f"Unsupported operation: {operation}")

            elif isinstance(payload, MethodCall):
                return self.method_call_request(msg)

        else:
            raise ValueError("Message is not of type GlacierMessage_v1")
        # Add a return statement for all code paths
        return GlacierMessage_v1(
            sender=msg.target,
            target=msg.sender,
            uuid_code=uuid.uuid4(),
            type=MessageType.ERROR,
            payload=msg.payload,
        )

    @override
    def read_request(self, msg: Message) -> Message:
        """
        This method reads a variable from the data model and returns a message with the
        variable value.
        :param msg: The message containing the variable name to be read.
        :return: A message with the variable value.
        """
        if isinstance(msg, GlacierMessage_v1) and isinstance(msg.payload, VariableCall):
            varname = msg.payload.varname
            value = self._data_model.read_variable(varname)
            response = GlacierMessage_v1(
                sender=msg.target,
                target=msg.sender,
                uuid_code=uuid.uuid4(),
                type=MessageType.SUCCESS,
                payload=VariableCall(varname, VarOperation.READ, args=value),
            )
            return response
        else:
            raise ValueError("Message is not of type GlacierMessage_v1")

    @override
    def write_request(self, msg: Message) -> Message:
        """
        This method writes a variable to the data model and returns a message with the
        variable value.
        :param msg: The message containing the variable name and value to be written.
        :return: A message with the variable value.
        """
        if isinstance(msg, GlacierMessage_v1) and isinstance(msg.payload, VariableCall):
            value = msg.payload.args
            varname = msg.payload.varname
            self._data_model.write_variable(varname, value)
            response = GlacierMessage_v1(
                sender=msg.target,
                target=msg.sender,
                uuid_code=uuid.uuid4(),
                type=MessageType.SUCCESS,
                payload=VariableCall(varname, VarOperation.WRITE, args=value),
            )
            return response
        else:
            raise ValueError("Message is not of type GlacierMessage_v1")

    @override
    def method_call_request(self, msg: Message) -> Message:
        """
        This method calls a method on the data model and returns a message with the
        method name and arguments.
        :param msg: The message containing the method name and arguments.
        :return: A message with the method name and arguments.
        """
        if isinstance(msg, GlacierMessage_v1) and isinstance(msg.payload, MethodCall):
            method_name = msg.payload.method
            args = msg.payload.args
            self._data_model.call_method(method_name, args)
            response = GlacierMessage_v1(
                sender=msg.target,
                target=msg.sender,
                uuid_code=uuid.uuid4(),
                type=MessageType.ACCEPTED,
                payload=MethodCall(method_name, args),
            )
            return response
        else:
            raise ValueError("Message is not of type GlacierMessage_v1")

    """
    @override
    def create_response(self, msg: Message) -> Message:
        return msg
    
    @override
    def parse_message(self, raw_msg: str) -> MessageGlacier_v1:
        return None          

    @override
    def subscribe_request(self, msg: MessageGlacier_v1) -> MessageGlacier_v1:
        return msg    
    """
