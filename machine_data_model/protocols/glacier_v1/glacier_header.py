from dataclasses import dataclass
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
    """

    NODE = "NODE"
    VARIABLE = "VARIABLE"
    METHOD = "METHOD"


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


class SpecialHeader(MsgName):
    """
    Enum for special headers.

    :cvar INIT_HANDSHAKE: Initialization handshake.
    """

    INIT_HANDSHAKE = "INIT_HANDSHAKE"


@dataclass(init=True, slots=True)
class GlacierHeader:
    """
    Represents the header of a message, and holds its metadata.

    :cvar type: The type of the message (e.g., REQUEST, RESPONSE, ERROR).
    :cvar version: The version of the protocol, represented as a tuple of integers (major, minor, patch).
    :cvar namespace: The namespace to which the message belongs (e.g., NODE, VARIABLE, METHOD).
    :cvar msg_name: The specific name of the message that describes its purpose or action (e.g., GET_INFO, READ).
    """

    type: MsgType
    version: tuple[int, int, int]
    namespace: MsgNamespace
    msg_name: MsgName
