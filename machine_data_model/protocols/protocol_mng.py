from abc import ABC, abstractmethod
from machine_data_model.data_model import DataModel
from dataclasses import dataclass


@dataclass(init=True, slots=True)
class Message(ABC):
    """
    Abstract base class representing a message in the protocol.
    """

    pass


class ProtocolMng(ABC):
    """
    Abstract class responsible for handling messages encoded with a specific protocol
    and updating the machine data model accordingly.

    :ivar _data_model: The machine data model that is updated based on the processed messages.
    """

    def __init__(self, data_model: DataModel):
        """
        Initializes the ProtocolMng with a specific machine data model.

        :param data_model: The machine data model to be used for updating based on the processed messages.
        """

        self._data_model = data_model

    @abstractmethod
    def handle_message(self, msg: Message) -> Message:
        """
        Abstract method to handle a protocol-specific message and update the
        machine data model.

        :param msg: The message to be handled, which should be an instance of the appropriate protocol message.
        :return: A response message based on the handling of the input message.
        """

        pass

    def get_data_model(self) -> DataModel:
        """
        Returns the machine data model.

        :return: The current machine data model used by the protocol manager.
        """
        return self._data_model

    # This class should be responsible for parsing the msgs and calling the
    # respective methods on the machine data model to handle the messages.
    # Note that the protocol manager is responsible for parsing the messages and
    # creating the correct response messages.
