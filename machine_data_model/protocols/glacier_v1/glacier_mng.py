from typing_extensions import override

from machine_data_model.data_model import DataModel
from machine_data_model.protocols.protocol_mng import (
    ProtocolMng,
    MessageRequest,
    MessageResponse,
)


class GlacierMng(ProtocolMng):
    """
    This class is responsible for handling messages encoded with the Glacier protocol
    and updating the machine data model accordingly.
    """

    def __init__(self, data_model: DataModel):
        super().__init__(data_model)

    @override
    def handle_message(self, msg: MessageRequest) -> MessageResponse:
        # TODO: MessageRequest and MessageResponse must be changed
        # call the specific method to handle the message
        # e.g. if msg.type == READ -> self._handle_read_request(msg)
        return MessageResponse()

    # if some methods can be shared between different protocols implementation they
    # should be implemented in the ProtocolMng class and called here!

    # def _handle_read_request(self, msg: ReadRequest) -> ReadResponse:
    #     pass
    # similar methods for other types of messages, e.g. write requests, subscribe
    # requests, method call requests, etc.
