import uuid
from typing import Any
from dataclasses import dataclass
from machine_data_model.protocols.glacier_v1.enumeration_for_messages import (
    MessageType,
)
from machine_data_model.protocols.glacier_v1.message import Message
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
from machine_data_model.protocols.glacier_v1.variable_message import VariableCall


@dataclass(init = True)
class MessageBuilder:
    sender = ""
    target = ""
    uuid_code = uuid.uuid4()
    topology:MessageType = MessageType.REQUEST
    payload:Any = None

    def set_sender(self, sender: str) -> "MessageBuilder":
        self.sender = sender
        return self

    def set_target(self, target: str) -> "MessageBuilder":
        self.target = target
        return self

    def set_uuid_code(self, uuid_code: uuid.UUID) -> "MessageBuilder":
        self.uuid_code = uuid_code
        return self

    def set_topology(self, topology: MessageType) -> "MessageBuilder":
        self.topology = topology
        return self

    def set_variable_payload(self, payload: VariableCall) -> "MessageBuilder":
        self.payload = payload
        return self

    def set_method_payload(self, payload: MethodCall) -> "MessageBuilder":
        self.payload = payload
        return self

    def build(self) -> Message:
        if not self.sender or not self.target or not self.payload:
            raise ValueError("Sender, target, and payload must be set")
        return Message(
            sender=self.sender,
            target=self.target,
            uuid_code=self.uuid_code,
            topology=self.topology,
            payload=self.payload,
        )
