from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from machine_data_model.nodes.subscription.variable_subscription import EventType


@dataclass(init=True, slots=True)
class FrostPayload:
    """
    Abstract base class for the payload of a message in the Frost protocol.

    Attributes:
        node (str): The node associated with the message payload.
    """

    node: str = ""


@dataclass(init=True, slots=True)
class VariablePayload(FrostPayload):
    """
    Represents the payload of a variable-related message.

    Attributes:
        value (Any): The value of the variable in the message payload.
    """

    value: Any = None


@dataclass(init=True, slots=True)
class SubscriptionPayload(VariablePayload):
    """
    Represents the payload of a subscription-related message.
    """

    @property
    def subscription_type(self) -> EventType:
        """
        Returns the type of the subscription.

        Returns:
            EventType: The type of the subscription.
        """
        return EventType.ANY


@dataclass(init=True, slots=True)
class DataChangeSubscriptionPayload(SubscriptionPayload):
    """
    Represents the payload of a data change subscription message.

    Attributes:
        deadband (float): Minimum change required to trigger a notification.
        is_percent (bool): If True, deadband is a percentage; otherwise, it's an absolute value.
    """

    deadband: float = 0.0
    is_percent: bool = False

    @property
    def subscription_type(self) -> EventType:
        """
        Returns the type of the subscription.

        Returns:
            EventType: The type of the subscription.
        """
        return EventType.DATA_CHANGE


@dataclass(init=True, slots=True)
class InRangeSubscriptionPayload(SubscriptionPayload):
    """
    Represents the payload of an in-range subscription message.

    Attributes:
        low (float): The lower bound of the range.
        high (float): The upper bound of the range.
    """

    low: float = 0.0
    high: float = 0.0

    @property
    def subscription_type(self) -> EventType:
        """
        Returns the type of the subscription.

        Returns:
            EventType: The type of the subscription.
        """
        return EventType.IN_RANGE


@dataclass(init=True, slots=True)
class OutOfRangeSubscriptionPayload(InRangeSubscriptionPayload):
    """
    Represents the payload of an out-of-range subscription message.
    """

    @property
    def subscription_type(self) -> EventType:
        """
        Returns the type of the subscription.

        Returns:
            EventType: The type of the subscription.
        """
        return EventType.OUT_OF_RANGE


@dataclass(init=True, slots=True)
class MethodPayload(FrostPayload):
    """
    Represents the payload of a method-related message.

    Attributes:
        args (list[Any]): The list of arguments for the method.
        kwargs (dict[str, Any]): The dictionary of keyword arguments for the method.
        ret (dict[str, Any]): The dictionary of return values from the method.
    """

    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    ret: dict[str, Any] = field(default_factory=dict)


@dataclass(init=True, slots=True)
class ProtocolPayload(FrostPayload):
    """
    Represents the payload of a protocol-related message.
    """

    pass


class ErrorCode(int, Enum):
    """
    Enum for error codes used in the Frost protocol.

    :cvar UNKNOWN: General unknown error.
    :cvar BAD_REQUEST: The request is invalid.
    :cvar NOT_FOUND: The requested node or resource was not found.
    :cvar NOT_ALLOWED: The requested operation is not allowed.
    :cvar NOT_SUPPORTED: The requested operation is not supported.
    :cvar NOT_IMPLEMENTED: The requested operation is not implemented.
    :cvar VERSION_NOT_SUPPORTED: The requested version of the protocol is not supported.
    """

    UNKNOWN = -1
    BAD_REQUEST = 100
    NOT_FOUND = 101
    NOT_ALLOWED = 102
    NOT_SUPPORTED = 103
    NOT_IMPLEMENTED = 104
    VERSION_NOT_SUPPORTED = 105
    BAD_RESPONSE = 200


class ErrorMessages(str, Enum):
    """
    Enum for error messages associated with the Frost protocol errors.

    :cvar INVALID_NAMESPACE: Error message for invalid namespace.
    :cvar INVALID_REQUEST: Error message for invalid request.
    :cvar NODE_NOT_FOUND: Error message for node not found.
    :cvar NOT_SUPPORTED: Error message for unsupported operation.
    :cvar BAD_REQUEST: Error message for bad request.
    :cvar NOT_ALLOWED: Error message for not allowed operation.
    :cvar VERSION_NOT_SUPPORTED: Error message for unsupported protocol version.
    """

    INVALID_NAMESPACE = "Invalid namespace"
    INVALID_REQUEST = "Invalid request"
    INVALID_RESPONSE = "Invalid response"
    NODE_NOT_FOUND = "Node not found"
    NOT_SUPPORTED = "The requested operation is not supported on the specified node"
    BAD_REQUEST = "Bad request"
    NOT_ALLOWED = "The requested operation is not allowed on the specified node"
    VERSION_NOT_SUPPORTED = "The requested version of the protocol is not supported"
    BAD_RESPONSE = "The response is invalid or malformed"


@dataclass(init=True, slots=True)
class ErrorPayload(FrostPayload):
    """
    Represents the payload of an error message in the Frost protocol.

    Attributes:
        error_code (int): The error code associated with the error message.
        error_message (str): A description of the error.
    """

    error_code: int = -1
    error_message: str = ""
