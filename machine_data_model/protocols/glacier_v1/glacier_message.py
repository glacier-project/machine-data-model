from machine_data_model.protocols.protocol_mng import Message
from dataclasses import dataclass
from machine_data_model.protocols.glacier_v1.glacier_header import GlacierHeader
from machine_data_model.protocols.glacier_v1.glacier_payload import Payload


@dataclass(init=True, slots=True)
class GlacierMessage(Message):
    """
    This class holds the core data of a message.

    :ivar sender: The sender of the message.
    :ivar target: The target of the message.
    :ivar identifier: The unique identifier of the message.
    :ivar header: The header containing message metadata.
    :ivar payload: The payload or data sent with the message.
    """

    sender: str
    target: str
    identifier: str
    header: GlacierHeader
    payload: Payload
