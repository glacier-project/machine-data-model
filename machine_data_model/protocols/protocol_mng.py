from abc import ABC, abstractmethod
from machine_data_model.data_model import DataModel
from dataclasses import dataclass


@dataclass(init=True, slots=True)
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
        """
        Abstract method called to handle a message encoded with a specific protocol and
        update the machine data model accordingly.
        """
        pass

    def get_data_model(self) -> DataModel:
        """
        Get the machine data model.
        """
        return self._data_model

    # This class should be responsible for parsing the msgs and calling the
    # respective methods on the machine data model to handle the messages.
    # Note that the protocol manager is responsible for parsing the messages and creating
    # the correct response messages.
