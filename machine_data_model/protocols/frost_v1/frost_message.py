"""Frost protocol message implementation.

This module defines the FrostMessage dataclass which represents messages in the
Frost protocol, containing sender, target, header, and payload information.
"""

from dataclasses import dataclass

from machine_data_model.protocols.frost_v1.frost_header import FrostHeader
from machine_data_model.protocols.frost_v1.frost_payload import FrostPayload
from machine_data_model.protocols.message import Message


@dataclass(init=True, slots=True, frozen=True)
class FrostMessage(Message):
    """This class holds the core data of a message.

    Attributes:
        sender (str):
            The sender of the message.
        target (str):
            The target of the message.
        header (FrostHeader):
            The header containing message metadata.
        payload (FrostPayload):
            The payload or data sent with the message.
    """

    sender: str
    target: str
    header: FrostHeader
    payload: FrostPayload
