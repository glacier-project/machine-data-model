from abc import ABC, abstractmethod
from machine_data_model.data_model import DataModel


class Message(ABC):
    pass


class ProtocolMng(ABC):
    """
    This abstract class is responsible for handling messages encoded with a specific
    protocol and updating the machine data model accordingly.
    """

    def __init__(self, data_model: DataModel):
        self._data_model = data_model

    @abstractmethod
    def handle_message(self, msg: Message) -> Message:
        pass

    # This class should be responsible for parsing the msgs and calling the
    # respective methods on the machine data model to handle the messages.
    # Note that the protocol manager is responsible for parsing the messages and creating
    # the correct response messages.
    @abstractmethod
    def parse_message(self, raw_msg: str) -> Message:
        pass

    @abstractmethod
    def create_response(self, msg: Message) -> Message:
        pass

    @abstractmethod
    def read_request(self, msg: Message) -> Message:
        pass

    @abstractmethod
    def write_request(self, msg: Message) -> Message:
        pass

    @abstractmethod
    def subscribe_request(self, msg: Message) -> Message:
        pass

    @abstractmethod
    def method_call_request(self, msg: Message) -> Message:
        pass

    @abstractmethod
    def unsubscribe_request(self, msg: Message) -> Message:
        pass
