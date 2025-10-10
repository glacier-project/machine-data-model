"""
Frost protocol header definitions.

This module defines the header structures for Frost protocol messages, including
message types, namespaces, names, and the FrostHeader dataclass.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class MsgType(str, Enum):
    """
    Enum for message types.

    Attributes:
        REQUEST:
            Request message.
        RESPONSE:
            Response message.
        ERROR:
            Error message.
    """

    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    # TODO: event
    ERROR = "ERROR"


class MsgNamespace(str, Enum):
    """
    Enum for message namespaces.

    Attributes:
        NODE:
            Node-related messages.
        VARIABLE:
            Variable-related messages.
        METHOD:
            Method-related messages.
        PROTOCOL:
            Protocol-related messages.
    """

    NODE = "NODE"
    VARIABLE = "VARIABLE"
    METHOD = "METHOD"
    PROTOCOL = "PROTOCOL"


class MsgName(str, Enum):
    pass


class NodeMsgName(MsgName):
    """
    Enum for node-related message names.

    Attributes:
        GET_INFO:
            Request node information.
        GET_CHILDREN:
            Request node children.
        GET_VARIABLES:
            Request node variables.
        GET_METHODS:
            Request node methods.
    """

    GET_INFO = "GET_INFO"
    GET_CHILDREN = "GET_CHILDREN"
    GET_VARIABLES = "GET_VARIABLES"
    GET_METHODS = "GET_METHODS"


class VariableMsgName(MsgName):
    """
    Enum for variable node-related message names.

    Attributes:
        READ:
            Read a variable node.
        WRITE:
            Write a variable node.
        SUBSCRIBE:
            Subscribe to a variable node.
        UNSUBSCRIBE:
            Unsubscribe from a variable node.
        UPDATE:
            Update a variable node.
    """

    READ = "READ"
    WRITE = "WRITE"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    UPDATE = "UPDATE"


class MethodMsgName(MsgName):
    """
    Enum for method-related message names.

    Attributes:
        INVOKE:
            Invoke a method.
        STARTED:
            Method started.
        COMPLETED:
            Method completed.
    """

    INVOKE = "INVOKE"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"


class ProtocolMsgName(MsgName):
    """
    Enum for protocol-related message names.

    Attributes:
        REGISTER:
            Registers the machine to the bus.
        UNREGISTER:
            Unregisters the machine to the bus.
    """

    REGISTER = "REGISTER"
    UNREGISTER = "UNREGISTER"


@dataclass(init=True, slots=True)
class FrostHeader:
    """
    Represents the header of a message, and holds its metadata.

    Attributes:
        type (MsgType):
            The type of the message (e.g., REQUEST, RESPONSE, ERROR).
        version (tuple[int, int, int]):
            The version of the protocol, represented as a tuple of integers
            (major, minor, patch).
        namespace (MsgNamespace):
            The namespace to which the message belongs (e.g., NODE, VARIABLE,
            METHOD).
        msg_name (MsgName):
            The specific name of the message that describes its purpose or
            action (e.g., GET_INFO, READ).
        timestamp (datetime):
            The timestamp when the message was created.
    """

    type: MsgType
    version: tuple[int, int, int]
    namespace: MsgNamespace
    msg_name: MsgName
    timestamp: datetime = datetime.now(timezone.utc)

    def matches(
        self,
        _type: Optional[MsgType] = None,
        _namespace: Optional[MsgNamespace] = None,
        _msg_name: Optional[MsgName] = None,
    ) -> bool:
        """
        Checks if the header matches the given type, namespace, and message
        name.

        Args:
            _type (Optional[MsgType]):
                The expected message type (e.g., REQUEST, RESPONSE). If None, it
                is ignored.
            _namespace (Optional[MsgNamespace]):
                The expected namespace (e.g., VARIABLE, METHOD, PROTOCOL). If
                None, it is ignored.
            _msg_name (Optional[MsgName]):
                The expected message name (e.g., REGISTER, READ, WRITE). If
                None, it is ignored.

        Returns:
            bool:
                True if the header matches all provided parameters, False
                otherwise.
        """

        return (
            (_type is None or self.type == _type)
            and (_namespace is None or self.namespace == _namespace)
            and (_msg_name is None or self.msg_name == _msg_name)
        )

    def __str__(self) -> str:
        """
        Returns a string representation of the FrostHeader.

        The format will be:
            Type: REQUEST, Version: 1.0.0, Namespace: VARIABLE, Message Name:
            READ, Timestamp: 2023-02-28T14:20:00+00:00
        """
        return (
            f"Type: {self.type}, "
            f"Version: {'.'.join(map(str, self.version))}, "
            f"Namespace: {self.namespace}, "
            f"Message Name: {self.msg_name}, "
            f"Timestamp: {self.timestamp.isoformat()}"
        )

    def __repr__(self) -> str:
        """
        Returns an official string representation of the FrostHeader.

        The format will be:
            FrostHeader(type='REQUEST', version=(1, 0, 0), namespace='VARIABLE',
                msg_name='READ', timestamp=datetime.datetime(2023, 2, 28, 14,
                20, 0, 123456, tzinfo=datetime.timezone.utc)
            )
        """
        return (
            f"FrostHeader(type={self.type!r}, "
            f"version={self.version!r}, "
            f"namespace={self.namespace!r}, "
            f"msg_name={self.msg_name!r}, "
            f"timestamp={self.timestamp!r})"
        )
