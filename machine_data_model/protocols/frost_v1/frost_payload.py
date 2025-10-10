"""
Frost protocol payload definitions.

This module defines various payload classes for different types of Frost
protocol messages, including variable operations, subscriptions, method calls,
and error handling.
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from machine_data_model.nodes.subscription.variable_subscription import EventType


@dataclass(init=True, slots=True)
class FrostPayload:
    """
    Abstract base class for the payload of a message in the Frost protocol.

    This class holds the general structure for the payload, which can be
    extended for different types of messages.

    Attributes:
        node (str):
            The node associated with the message payload.
    """

    node: str = ""


@dataclass(init=True, slots=True)
class VariablePayload(FrostPayload):
    """
    Represents the payload of a variable-related message.

    This class extends the base payload and includes the value associated with
    the variable message.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
        value (Any):
            The value of the variable in the message payload.
    """

    value: Any = None


@dataclass(init=True, slots=True)
class SubscriptionPayload(VariablePayload):
    """
    Represents the payload of a subscription-related message.

    This class extends the subscription payload and includes attributes that are
    need to handle subscription-related messages.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
    """

    @property
    def subscription_type(self) -> EventType:
        return EventType.ANY


@dataclass(init=True, slots=True)
class DataChangeSubscriptionPayload(SubscriptionPayload):
    """
    Represents the payload of a data change subscription message.

    This class extends the subscription payload and includes attributes specific
    to data change subscriptions.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
        deadband (float):
            Minimum change required to trigger a notification.
        is_percent (bool):
            If True, deadband is treated as a percentage of the previous value;
            otherwise, it's an absolute value.
    """

    deadband: float = 0.0
    is_percent: bool = False

    @property
    def subscription_type(self) -> EventType:
        return EventType.DATA_CHANGE


@dataclass(init=True, slots=True)
class InRangeSubscriptionPayload(SubscriptionPayload):
    """
    Represents the payload of an in-range subscription message.

    This class extends the subscription payload and includes attributes specific
    to in-range subscriptions.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
        low (float):
            The lower bound of the range.
        high (float):
            The upper bound of the range.
    """

    low: float = 0.0
    high: float = 0.0

    @property
    def subscription_type(self) -> EventType:
        return EventType.IN_RANGE


@dataclass(init=True, slots=True)
class OutOfRangeSubscriptionPayload(InRangeSubscriptionPayload):
    """
    Represents the payload of an out-of-range subscription message.

    This class extends the subscription payload and includes attributes specific
    to out-of-range subscriptions.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
        low (float):
            The lower bound of the range.
        high (float):
            The upper bound of the range.
    """

    @property
    def subscription_type(self) -> EventType:
        return EventType.OUT_OF_RANGE


@dataclass(init=True, slots=True)
class MethodPayload(FrostPayload):
    """
    Represents the payload of a method-related message.

    This class extends the base payload and includes arguments, keyword
    arguments, and return values for method invocations.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
        args (list[Any]):
            The list of arguments for the method.
        kwargs (dict[str, Any]):
            The dictionary of keyword arguments for the method.
        ret (dict[str, Any]):
            The dictionary of return values from the method.
    """

    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    ret: dict[str, Any] = field(default_factory=dict)


@dataclass(init=True, slots=True)
class ProtocolPayload(FrostPayload):
    """
    Represents the payload of a protocol-related message.

    This class extends the base payload and includes attributes that are need to
    handle protocol-related messages.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
    """

    pass


class ErrorCode(int, Enum):
    """
    Enum for error codes used in the Frost protocol.

    Attributes:
        UNKNOWN:
            General unknown error.
        BAD_REQUEST:
            The request is invalid.
        NOT_FOUND:
            The requested node or resource was not found.
        NOT_ALLOWED:
            The requested operation is not allowed.
        NOT_SUPPORTED:
            The requested operation is not supported.
        NOT_IMPLEMENTED:
            The requested operation is not implemented.
        VERSION_NOT_SUPPORTED:
            The requested version of the protocol is not supported.
        BAD_RESPONSE:
            The response is invalid or malformed.
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

    Attributes:
        INVALID_NAMESPACE:
            Error message for invalid namespace.
        INVALID_REQUEST:
            Error message for invalid request.
        INVALID_RESPONSE:
            Error message for invalid response.
        NODE_NOT_FOUND:
            Error message for node not found.
        NOT_SUPPORTED:
            Error message for unsupported operation.
        BAD_REQUEST:
            Error message for bad request.
        NOT_ALLOWED:
            Error message for not allowed operation.
        VERSION_NOT_SUPPORTED:
            Error message for unsupported protocol version.
        BAD_RESPONSE:
            Error message for invalid or malformed response.
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

    This class extends the base payload and includes error-related information.

    Attributes:
        node (str):
            The node associated with the message payload (inherited).
        error_code (int):
            The error code associated with the error message.
        error_message (str):
            A description of the error.
    """

    error_code: int = -1
    error_message: str = ""
