"""
A module defining the MessageBuilder abstract base class for building and parsing messages.

This module provides an abstract base class `MessageBuilder` that outlines the
structure for building and parsing messages in a communication protocol. It includes
methods for getting and setting the sender of the message, as well as abstract methods
for parsing and serializing messages.
"""

from abc import ABC, abstractmethod
from typing import Any
from machine_data_model.protocols.message import Message


class MessageBuilder(ABC):
    def __init__(self, sender: str):
        self._sender = sender

    def get_sender(self) -> str:
        """Return the sender of the message.

        Returns:
            str:
                The sender of the message.
        """
        return self._sender

    def set_sender(self, sender: str) -> None:
        """Set the sender of the message.

        Args:
            sender (str):
                The sender to be set.
        """
        self._sender = sender
