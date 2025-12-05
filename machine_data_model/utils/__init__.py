"""
Utility functions and classes for the machine data model.
"""

from .timestamp import (
    get_timestamp_ns,
    get_timestamp_provider,
    reset_timestamp_provider,
    set_timestamp_provider,
)

__all__ = [
    "get_timestamp_ns",
    "get_timestamp_provider",
    "reset_timestamp_provider",
    "set_timestamp_provider",
]
