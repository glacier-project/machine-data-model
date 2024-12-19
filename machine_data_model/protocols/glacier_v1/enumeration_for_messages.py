from enum import Enum


class MessageType(Enum):
    REQUEST = 1
    SUCCESS = 2
    ERROR = 3
    ACCEPTED = 4
