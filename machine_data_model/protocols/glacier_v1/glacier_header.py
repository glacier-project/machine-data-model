from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


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


class ProtocolMsgName(MsgName):
    """
    Enum for protocol-related message names.

    :cvar REGISTER: Registers the machine to the bus.
    :cvar UNREGISTER: Unregisters the machine to the bus.
    """

    REGISTER = "REGISTER"
    UNREGISTER = "UNREGISTER"


@dataclass(init=True, slots=True)
class GlacierHeader:
    """
    Represents the header of a message, and holds its metadata.

    :cvar type: The type of the message (e.g., REQUEST, RESPONSE, ERROR).
    :cvar version: The version of the protocol, represented as a tuple of integers (major, minor, patch).
    :cvar namespace: The namespace to which the message belongs (e.g., NODE, VARIABLE, METHOD).
    :cvar msg_name: The specific name of the message that describes its purpose or action (e.g., GET_INFO, READ).
    :cvar timestamp: The timestamp when the message was created.
    """

    type: MsgType
    version: tuple[int, int, int]
    namespace: MsgNamespace
    msg_name: MsgName
    timestamp: datetime = datetime.now(timezone.utc)

    def matches(
        self, _type: MsgType, _namespace: MsgNamespace, _msg_name: MsgName
    ) -> bool:
        """
        Checks if the header matches the given type, namespace, and message name.

        :param _type: The expected message type (e.g., REQUEST, RESPONSE).
        :param _namespace: The expected namespace (e.g., VARIABLE, METHOD, PROTOCOL).
        :param _msg_name: The expected message name (e.g., REGISTER, READ, WRITE).
        :return: True if the header matches the given parameters, False otherwise.
        """

        return (
            self.type == _type
            and self.namespace == _namespace
            and self.msg_name == _msg_name
        )

    def __str__(self) -> str:
        """
        Returns a string representation of the GlacierHeader.

        The format will be:
            Type: REQUEST, Version: 1.0.0, Namespace: VARIABLE, Message Name: READ, Timestamp: 2023-02-28T14:20:00+00:00
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
        Returns an official string representation of the GlacierHeader.

        The format will be:
            GlacierHeader(type='REQUEST', version=(1, 0, 0), namespace='VARIABLE',
                msg_name='READ',
                timestamp=datetime.datetime(2023, 2, 28, 14, 20, 0, 123456, tzinfo=datetime.timezone.utc)
            )
        """
        return (
            f"GlacierHeader(type={self.type!r}, "
            f"version={self.version!r}, "
            f"namespace={self.namespace!r}, "
            f"msg_name={self.msg_name!r}, "
            f"timestamp={self.timestamp!r})"
        )
