"""
Frost protocol message implementation.

This module defines the FrostMessage dataclass which represents messages in the
Frost protocol, containing sender, target, header, and payload information.
"""

import uuid
from dataclasses import dataclass, field

from machine_data_model.protocols.frost_v1.frost_header import FrostHeader
from machine_data_model.protocols.frost_v1.frost_payload import FrostPayload
from machine_data_model.protocols.message import Message


@dataclass(init=True, slots=True)
class FrostMessage(Message):
    """
    This class holds the core data of a message.

    Attributes:
        sender (str):
            The sender of the message.
        target (str):
            The target of the message.
        header (FrostHeader):
            The header containing message metadata.
        payload (FrostPayload):
            The payload or data sent with the message.
        identifier (str):
            The unique identifier of the message.
        correlation_id (str):
            The correlation ID for tracking the message.

    """

    sender: str
    target: str
    header: FrostHeader
    payload: FrostPayload
    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
