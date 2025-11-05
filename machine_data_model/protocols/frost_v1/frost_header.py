from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class MsgType(str, Enum):
    """
    Enum for message types.

    :cvar REQUEST: Request message.
    :cvar RESPONSE: Response message.
    :cvar ERROR: Error message.

    :todo: Add support for event types.
    """

    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    # TODO: event
    ERROR = "ERROR"


class MsgNamespace(str, Enum):
    """
    Enum for message namespaces.

    :cvar NODE: Node-related messages.
    :cvar VARIABLE: Variable-related messages.
    :cvar METHOD: Method-related messages.
    :cvar PROTOCOL: Protocol-related messages.
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

    :cvar GET_INFO: Request node information.
    :cvar GET_CHILDREN: Request node children.
    :cvar GET_VARIABLES: Request node variables.
    :cvar GET_METHODS: Request node methods.
    """

    GET_INFO = "GET_INFO"
    GET_CHILDREN = "GET_CHILDREN"
    GET_VARIABLES = "GET_VARIABLES"
    GET_METHODS = "GET_METHODS"


class VariableMsgName(MsgName):
    """
    Enum for variable node-related message names.

    :cvar READ: Read a variable node.
    :cvar WRITE: Write a variable node.
    :cvar SUBSCRIBE: Subscribe to a variable node.
    :cvar UNSUBSCRIBE: Unsubscribe from a variable node.
    :cvar UPDATE: Update a variable node.
    """

    READ = "READ"
    WRITE = "WRITE"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    UPDATE = "UPDATE"


class MethodMsgName(MsgName):
    """
    Enum for method-related message names.

    :cvar INVOKE: Invoke a method.
    """

    INVOKE = "INVOKE"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"


class ProtocolMsgName(MsgName):
    """
    Enum for protocol-related message names.

    :cvar REGISTER: Registers the machine to the bus.
    :cvar UNREGISTER: Unregisters the machine to the bus.
    """

    REGISTER = "REGISTER"
    UNREGISTER = "UNREGISTER"


@dataclass(init=True, slots=True)
class FrostHeader:
    """
    Represents the header of a message and holds its metadata.

    Attributes:
        type (MsgType): The type of the message (e.g., REQUEST, RESPONSE, ERROR).
        version (tuple[int, int, int]): The version of the protocol.
        namespace (MsgNamespace): The namespace of the message (e.g., NODE, VARIABLE, METHOD).
        msg_name (MsgName): The specific name of the message.
        timestamp (datetime): The timestamp when the message was created.
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
        Checks if the header matches the given type, namespace, and message name.

        Args:
            _type (Optional[MsgType]): The message type to match.
            _namespace (Optional[MsgNamespace]): The namespace to match.
            _msg_name (Optional[MsgName]): The message name to match.

        Returns:
            bool: True if the header matches, False otherwise.
        """

        return (
            (_type is None or self.type == _type)
            and (_namespace is None or self.namespace == _namespace)
            and (_msg_name is None or self.msg_name == _msg_name)
        )

    def __str__(self) -> str:
        """
        Returns a string representation of the FrostHeader.

        Returns:
            str: The string representation of the header.
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

        Returns:
            str: The official string representation of the header.
        """
        return (
            f"FrostHeader(type={self.type!r}, "
            f"version={self.version!r}, "
            f"namespace={self.namespace!r}, "
            f"msg_name={self.msg_name!r}, "
            f"timestamp={self.timestamp!r})"
        )
