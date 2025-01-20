import uuid
from abc import ABC
from enum import Enum
from machine_data_model.protocols.protocol_mng import Message


class MessageType(Enum):
    REQUEST = 1
    SUCCESS = 2
    ERROR = 3
    ACCEPTED = 4
    REJECTED = 5

    def __str__(self) -> str:
        return self.name


class Payload(ABC):
    pass


class GlacierMessage_v1(Message):
    sender: str
    target: str
    uuid_code: uuid.UUID
    type: MessageType
    payload: Payload

    def __init__(
        self,
        sender: str,
        target: str,
        uuid_code: uuid.UUID,
        type: MessageType,
        payload: Payload,
    ):
        self.sender = sender
        self.target = target
        self.uuid_code = uuid_code
        self.type = type
        self.payload = payload

    @property
    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "target": self.target,
            "uuid_code": uuid.UUID,
            "type": self.type.name,
            "payload": self.payload,
        }

    def __str__(self) -> str:
        return (
            f"Message("
            f"sender={self.sender}, "
            f"target={self.target}, "
            f"uuid_code={self.uuid_code}, "
            f"type={self.type}, "
            f"payload={self.payload})"
        )

    def __repr__(self) -> str:
        return self.__str__()
