from enum import Enum
from machine_data_model.protocols.glacier_v1.enumeration_for_messages import MessageTopology
from dataclasses import dataclass
import uuid
from typing import Any
from typing_extensions import override


@dataclass(frozen=True)
class Message:
    sender:str 
    target:str 
    uuid_code:uuid.UUID
    topology:MessageTopology 
    payload: Any

    @property
    def get_payload(self):
        return self.payload
    @property
    def get_uuid(self):
        return self.uuid_code
    @property
    def get_topology(self):
        return self.topology
    @property
    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "target": self.target,
            "uuid_code": uuid.UUID,
            "topology": self.topology.name,
            "payload": self.payload
        }
    @property
    def from_dict(cls, data: dict) -> 'Message':
        return cls(
            sender=data["sender"],
            target=data["target"],
            uuid_code=uuid.UUID(data["uuid_code"]),
            topology=MessageTopology[data["topology"]],
            payload=data["payload"]
        )
    @override
    def __len__(self) -> int:
        return len(self.payload)
    @override
    def __iter__(self):
        return iter(self.payload)
    @override
    def __getitem__(self, index: int) -> Any:
        return self.payload[index]
    @override
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
    def __str__(self):
        return (
            f"Message("
            f"sender={self.sender}, "
            f"target={self.target}, "
            f"uuid_code={self.uuid_code}, "
            f"topology={self.topology}, "
            f"payload={self.payload})"
        )
    def __repr__(self):
        return self.__str__()