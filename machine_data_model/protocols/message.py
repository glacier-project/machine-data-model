from abc import ABC
from dataclasses import dataclass


@dataclass(init=True, slots=True)
class Message(ABC):
    """
    Abstract base class representing a message in the protocol.
    """

    pass
