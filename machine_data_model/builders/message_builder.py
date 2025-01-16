import uuid
from typing import Any
from dataclasses import dataclass
from machine_data_model.protocols.glacier_v1.message import (
    MessageType,
    GlacierMessage_v1,
)
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
from machine_data_model.protocols.glacier_v1.variable_message import VariableCall


@dataclass(init=False)
class GlacierMessageBuilder_v1:
    sender: str
    target: str
    uuid_code = uuid.uuid4()
    type: MessageType
    payload: Any

    def set_sender(self, sender: str) -> "GlacierMessageBuilder_v1":
        self.sender = sender
        return self

    def set_target(self, target: str) -> "GlacierMessageBuilder_v1":
        self.target = target
        return self

    def set_uuid_code(self, uuid_code: uuid.UUID) -> "GlacierMessageBuilder_v1":
        self.uuid_code = uuid_code
        return self

    def set_type(self, type: MessageType) -> "GlacierMessageBuilder_v1":
        self.type = type
        return self

    def set_variable_payload(self, payload: VariableCall) -> "GlacierMessageBuilder_v1":
        self.payload = payload
        return self

    def set_method_payload(self, payload: MethodCall) -> "GlacierMessageBuilder_v1":
        self.payload = payload
        return self

    def build(self) -> GlacierMessage_v1:
        if not self.sender or not self.target or not self.payload:
            raise ValueError("Sender, target, and payload must be set")
        return GlacierMessage_v1(
            sender=self.sender,
            target=self.target,
            uuid_code=self.uuid_code,
            type=self.type,
            payload=self.payload,
        )
