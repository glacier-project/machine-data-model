"""Error information produced by failed control flow executions.

This module is a leaf module: it does not import any node class, so it can be
imported from anywhere without creating import cycles.
"""

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

# Whitespace and control characters (C0, DEL, C1) in a text.
_CONTROL_RUNS = re.compile(r"[\s\x00-\x1f\x7f-\x9f]+")

# Unicode categories removed from a text: lone surrogates (Cs), which cannot be
# encoded, and format characters (Cf: bidi overrides, zero-width characters),
# which can hide or reorder text.
_REMOVED_CATEGORIES = frozenset({"Cs", "Cf"})

_ELLIPSIS = "..."


def sanitize_detail(text: str, max_length: int) -> str:
    """Make a text safe and bounded to be shown to a peer or written to a log.

    Lone surrogates and format characters (bidi controls, zero-width
    characters) are removed. Runs of whitespace and control characters
    (newlines, carriage returns, escape sequences, ...) become one space and
    the text is stripped. If it is longer than `max_length` characters it is
    cut on the string, never in the middle of a character or between a
    character and its combining marks, and "..." is appended: the ellipsis is
    part of the budget, so the result is never longer than `max_length` (for
    `max_length` below 3 the text is cut without an ellipsis).

    Args:
        text (str):
            The text.
        max_length (int):
            The longest result, in characters.

    Returns:
        str:
            The sanitized text, at most `max_length` characters long.

    """
    kept = "".join(
        char
        for char in text
        if unicodedata.category(char) not in _REMOVED_CATEGORIES
    )
    result = _CONTROL_RUNS.sub(" ", kept).strip()
    if len(result) <= max_length:
        return result
    keep = (
        max(max_length - len(_ELLIPSIS), 0) if max_length >= 3 else max_length
    )
    # Do not leave a base character without the combining marks that follow.
    while keep > 0 and unicodedata.category(result[keep]).startswith("M"):
        keep -= 1
    cut = result[:keep].rstrip()
    return cut + _ELLIPSIS if max_length >= 3 else cut


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
