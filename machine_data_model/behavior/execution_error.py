"""Error information produced by failed control flow executions.

This module is a leaf module: it does not import any node class, so it can be
imported from anywhere without creating import cycles.
"""

from dataclasses import dataclass
from enum import Enum
import re

# Whitespace and control characters (C0, DEL, C1) in a text.
_CONTROL_RUNS = re.compile(r"[\s\x00-\x1f\x7f-\x9f]+")


def sanitize_detail(text: str, max_length: int) -> str:
    """Make a text safe and bounded to be shown to a peer or written to a log.

    Runs of whitespace and control characters (newlines, carriage returns,
    escape sequences, ...) become one space, the text is stripped and cut to
    `max_length` characters (on the string, never in the middle of a
    character) with "..." appended when it was cut.

    Args:
        text (str):
            The text.
        max_length (int):
            The longest text kept, in characters.

    Returns:
        str:
            The sanitized text.

    """
    result = _CONTROL_RUNS.sub(" ", text).strip()
    if len(result) > max_length:
        result = result[:max_length].rstrip() + "..."
    return result


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
        observed (str | None):
            The value observed when a condition failed, as a bounded `repr`.
            For logs and traces only: it is never sent over Frost.

    """

    code: ExecutionErrorCode
    message: str
    node: str | None = None
    origin: str | None = None
    observed: str | None = None
