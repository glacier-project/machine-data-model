import uuid
from machine_data_model.protocols.message import Message
from dataclasses import dataclass
from machine_data_model.protocols.frost_v1.frost_header import FrostHeader
from machine_data_model.protocols.frost_v1.frost_payload import FrostPayload


@dataclass(init=True, slots=True)
class FrostMessage(Message):
    """
    This class holds the core data of a message.

    :ivar sender: The sender of the message.
    :ivar target: The target of the message.
    :ivar header: The header containing message metadata.
    :ivar payload: The payload or data sent with the message.
    :ivar identifier: The unique identifier of the message.
    :ivar correlation_id: The correlation ID for tracking the message.
    """

    sender: str
    target: str
    header: FrostHeader
    payload: FrostPayload
    identifier: str = str(uuid.uuid4())
    correlation_id: str = str(uuid.uuid4())
