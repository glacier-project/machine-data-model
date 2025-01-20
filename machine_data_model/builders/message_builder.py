import uuid
from typing import Any, Optional
from machine_data_model.protocols.glacier_v1.message import (
    GlacierMessage_v1,
    MessageType,
    Payload,
)
from machine_data_model.protocols.glacier_v1.variable_message import (
    VariableCall,
    VarOperation,
)
from machine_data_model.protocols.glacier_v1.method_message import MethodCall


class GlacierMessageBuilder_v1:
    """
    A class to build a GlacierMessage_v1 step by step.
    """

    def __init__(self) -> None:
        self._sender: Optional[str] = None
        self._target: Optional[str] = None
        self._uuid_code: Optional[uuid.UUID] = None
        self._type: Optional[MessageType] = None
        self._payload: Optional[Payload] = None
        self._reset()

    def _reset(self) -> None:
        """
        Reset the builder to its initial state.
        """
        self._sender = None
        self._target = None
        self._uuid_code = None
        self._type = None
        self._payload = None

    def set_sender(self, sender: str) -> "GlacierMessageBuilder_v1":
        self._sender = sender
        return self

    def set_target(self, target: str) -> "GlacierMessageBuilder_v1":
        self._target = target
        return self

    def set_uuid_code(self, uuid_code: uuid.UUID) -> "GlacierMessageBuilder_v1":
        self._uuid_code = uuid_code
        return self

    def set_type(self, type: MessageType) -> "GlacierMessageBuilder_v1":
        self._type = type
        return self

    def set_variable_payload(
        self, varname: str, operation: VarOperation, value: Any
    ) -> "GlacierMessageBuilder_v1":
        self._payload = VariableCall(varname=varname, operation=operation, args=value)
        return self

    def set_method_payload(self, method: str, value: Any) -> "GlacierMessageBuilder_v1":
        self._payload = MethodCall(method=method, args=value)
        return self

    def set_custom_payload(self, payload: Payload) -> "GlacierMessageBuilder_v1":
        self._payload = payload
        return self

    def build(self) -> GlacierMessage_v1:
        """
        Build a GlacierMessage_v1 instance with the provided values.
        This method ensures that all required fields (sender, target, type, and payload) are set.
        If any of these fields are missing, a ValueError is raised. A new UUID is generated if
        the uuid_code is not provided. After building the message, the builder is reset to its
        initial state for reuse.
        Returns:
            GlacierMessage_v1: The constructed GlacierMessage_v1 instance.
        Raises:
            ValueError: If any of the required fields (sender, target, type, payload) are not set.
        """
        if not self._sender or not self._target or not self._payload or not self._type:
            raise ValueError("Sender, target, type, and payload must be set")

        message = GlacierMessage_v1(
            sender=self._sender,
            target=self._target,
            uuid_code=self._uuid_code
            or uuid.uuid4(),  # Generate a new UUID if not provided
            type=self._type,
            payload=self._payload,
        )

        self._reset()

        return message
