from abc import ABC, abstractmethod

from machine_data_model.data_model import DataModel


#
class MessageRequest(ABC):
    pass


class MessageResponse(ABC):
    pass


class ProtocolMng(ABC):
    """
    This abstract class is responsible for handling messages encoded with a specific
    protocol and updating the machine data model accordingly.
    """

    def __init__(self, data_model: DataModel):
        self._data_model = data_model

    @abstractmethod
    def handle_message(self, msg: MessageRequest) -> MessageResponse:
        pass

    # TODO: This class should be responsible for parsing the msgs and calling the
    #  respective methods on the machine data model to handle the messages.
    # Note that the protocol manager is responsible for parsing the messages and creating
    # the correct response messages.
