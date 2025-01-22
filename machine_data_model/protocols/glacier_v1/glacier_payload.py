from dataclasses import dataclass, field
from typing import Any
from enum import Enum


@dataclass(init=True, slots=True)
class Payload:
    """
    This class is an abstract class that represents the payload of a message.
    """

    node: str = ""


@dataclass(init=True, slots=True)
class VariablePayload(Payload):
    """
    This class represents the payload of a variable message.
    """

    value: Any = None


@dataclass(init=True, slots=True)
class MethodPayload(Payload):
    """
    This class represents the payload of a method message.
    """

    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    ret: dict[str, Any] = field(default_factory=dict)


class ErrorCode(int, Enum):
    UNKNOWN = -1
    BAD_REQUEST = 100
    NOT_FOUND = 101
    NOT_ALLOWED = 102
    NOT_SUPPORTED = 103
    NOT_IMPLEMENTED = 104
    VERSION_NOT_SUPPORTED = 105


class ErrorMessages(str, Enum):
    INVALID_NAMESPACE = "Invalid namespace"
    INVALID_REQUEST = "Invalid request"
    NODE_NOT_FOUND = "Node not found"
    NOT_SUPPORTED = "The requested operation is not supported on the specified node"
    BAD_REQUEST = "Bad request"
    NOT_ALLOWED = "The requested operation is not allowed on the specified node"
    VERSION_NOT_SUPPORTED = "The requested version of the protocol is not supported"


@dataclass(init=True, slots=True)
class ErrorPayload(Payload):
    """
    This class represents the payload of an error message.
    """

    error_code: int = -1
    error_message: str = ""
