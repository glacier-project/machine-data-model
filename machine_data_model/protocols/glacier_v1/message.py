import uuid
from dataclasses import dataclass
from typing import Any

from typing_extensions import override

from machine_data_model.protocols.glacier_v1.enumeration_for_messages import (
    MessageType,
)


@dataclass(init = True)
class Message:
    sender: str
    target: str
    uuid_code: uuid.UUID
    topology: MessageType
    payload: Any

    def set_uuid_code(self, code :uuid.UUID) -> bool:
        self.uuid_code = code
        return True

    @property
    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "target": self.target,
            "uuid_code": uuid.UUID,
            "topology": self.topology.name,
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

    @override
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Message):
            return False
        return (
            self.sender == other.sender
            and self.target == other.target
            and self.uuid_code == other.uuid_code
            and self.topology == other.topology
            and self.payload == other.payload
        )

    def __str__(self) -> str:
        return (
            f"Message("
            f"sender={self.sender}, "
            f"target={self.target}, "
            f"uuid_code={self.uuid_code}, "
            f"topology={self.topology}, "
            f"payload={self.payload})"
        )

    def __repr__(self) -> str:
        return self.__str__()
