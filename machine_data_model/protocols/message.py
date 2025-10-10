"""
Protocol message base classes.

This module defines the base Message class that serves as the foundation for all
protocol-specific message implementations in the machine data model.
"""

from abc import ABC
from dataclasses import dataclass


@dataclass(init=True, slots=True)
class Message(ABC):
    """
    Abstract base class representing a message in the protocol.
    """

    pass
