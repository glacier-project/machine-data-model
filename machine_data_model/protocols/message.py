"""Protocol message base classes.

This module defines the base Message class that serves as the foundation for all
protocol-specific message implementations in the machine data model.
"""

from dataclasses import dataclass, field
import uuid


@dataclass(init=True, slots=True, frozen=True)
class Message:
    """Abstract base class representing a message in the protocol.

    Attributes:
        identifier (str):
            The unique identifier of the message.
        correlation_id (str):
            The correlation ID for tracking the message.
    """

    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
