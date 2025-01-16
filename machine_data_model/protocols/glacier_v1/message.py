import uuid
from typing import Any
from abc import ABC
from enum import Enum
from machine_data_model.protocols.protocol_mng import Message


class MessageType(Enum):
    REQUEST = 1
    SUCCESS = 2
    ERROR = 3
    ACCEPTED = 4


class Payload(ABC):
    pass


class GlacierMessage_v1(Message):
    sender: str
    target: str
    uuid_code: uuid.UUID
    type: MessageType
    payload: Any

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

    def set_uuid_code(self, code: uuid.UUID) -> bool:
        self.uuid_code = code
        return True

    @property
    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "target": self.target,
            "uuid_code": uuid.UUID,
            "type": self.type.name,
            "payload": self.payload,
        }

    def __len__(self) -> int:
        return len(self.payload)

    def __iter__(self) -> Any:
        return iter(self.payload)

    def __getitem__(self, index: int) -> Any:
        return self.payload[index]

    def __contains__(self, item: Any) -> bool:
        return item in self.payload

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, GlacierMessage_v1):
            return False
        return (
            self.sender == other.sender
            and self.target == other.target
            and self.uuid_code == other.uuid_code
            and self.type == other.type
            and self.payload == other.payload
        )

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
