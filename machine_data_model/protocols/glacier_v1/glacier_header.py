from dataclasses import dataclass
from enum import Enum


class MsgType(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    ERROR = "ERROR"


class MsgNamespace(str, Enum):
    NODE = "NODE"
    VARIABLE = "VARIABLE"
    METHOD = "METHOD"


class MsgName(str, Enum):
    pass


class NodeMsgName(MsgName):
    GET_INFO = "GET_INFO"
    GET_CHILDREN = "GET_CHILDREN"
    GET_VARIABLES = "GET_VARIABLES"
    GET_METHODS = "GET_METHODS"


class VariableMsgName(MsgName):
    READ = "READ"
    WRITE = "WRITE"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"


class MethodMsgName(MsgName):
    INVOKE = "INVOKE"


@dataclass(init=True, slots=True)
class GlacierHeader:
    """
    This class represents the header of a message. It contains the type of the message,
    the version of the protocol, the namespace and the name of the message.
    """

    type: MsgType
    version: tuple[int, int, int]
    namespace: MsgNamespace
    msg_name: MsgName
