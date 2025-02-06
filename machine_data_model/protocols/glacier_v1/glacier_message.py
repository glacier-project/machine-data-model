from machine_data_model.protocols.protocol_mng import Message
from dataclasses import dataclass
from machine_data_model.protocols.glacier_v1.glacier_header import (
    GlacierHeader,
    SpecialHeader,
)
from machine_data_model.protocols.glacier_v1.glacier_payload import Payload


@dataclass(init=True, slots=True)
class GlacierMessage(Message):
    sender: str
    target: str
    identifier: str
    header: GlacierHeader
    payload: Payload


# TODO: This is Glacier Message
@dataclass(init=True, slots=True)
class GlacierSpecialMessage(Message):
    sender: str
    target: str
    identifier: str
    header: SpecialHeader
