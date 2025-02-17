from machine_data_model.protocols.protocol_mng import Message
from dataclasses import dataclass
from machine_data_model.protocols.glacier_v1.glacier_header import (
    GlacierHeader,
    SpecialHeader,
)
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


# TODO: This is Glacier Message
@dataclass(init=True, slots=True)
class GlacierSpecialMessage(Message):
    """
    This class is similar to GlacierMessage but uses a different header type,
    and has no Payload.

    :ivar sender: The sender of the special message.
    :ivar target: The target of the special message.
    :ivar identifier: The unique identifier of the special message.
    :ivar header: The special header containing message metadata.

    :todo: Might be that the TODO, up there, referse to the fact that this could be a GlacierMessage? With an header, that uses a specific type of MsgType, called HANDSHAKE, maybe.
    """

    sender: str
    target: str
    identifier: str
    header: SpecialHeader
