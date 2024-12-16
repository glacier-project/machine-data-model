from enum import Enum


class MessageTopology(Enum):
    REQUEST = 1
    SUCCESS = 2
    ERROR = 3
    ACCEPTED = 4
