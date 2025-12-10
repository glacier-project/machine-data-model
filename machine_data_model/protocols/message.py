"""Protocol message base classes.

This module defines the base Message class that serves as the foundation for all
protocol-specific message implementations in the machine data model.
"""

from dataclasses import dataclass


@dataclass(init=True, slots=True, frozen=True)
class Message:
    """Base class representing a message in the protocol.
    """
