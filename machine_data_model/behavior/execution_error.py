"""Error information produced by failed control flow executions.

This module is a leaf module: it does not import any node class, so it can be
imported from anywhere without creating import cycles.
"""

from dataclasses import dataclass
from enum import Enum


class ExecutionErrorCode(str, Enum):
    """Enumeration of the reasons for which an execution can fail.

    Attributes:
        PRECONDITION_NOT_MET:
            A required condition evaluated to false.
        NO_DATA:
            A required condition could not be evaluated because a value is
            unavailable.
        TIMEOUT:
            A wait exceeded its deadline.
        INVALID_CONFIGURATION:
            The model is not configured correctly for the requested operation.
        REMOTE_ERROR:
            A remote party reported an error. Reserved, not produced yet.
        UNEXPECTED_ERROR:
            A node raised an exception that is not part of its contract.

    """

    PRECONDITION_NOT_MET = "precondition_not_met"
    NO_DATA = "no_data"
    TIMEOUT = "timeout"
    INVALID_CONFIGURATION = "invalid_configuration"
    REMOTE_ERROR = "remote_error"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class ExecutionError:
    """Describes why an execution failed.

    Attributes:
        code (ExecutionErrorCode):
            The machine-readable reason of the failure.
        message (str):
            A human-readable description of the failure.
        node (str | None):
            The qualified name of the node that failed, if any.
        origin (str | None):
            The node where the error was first raised. It is preserved when
            the error is propagated through callers, while `node` and
            `message` describe the node that reports it.

    """

    code: ExecutionErrorCode
    message: str
    node: str | None = None
    origin: str | None = None
