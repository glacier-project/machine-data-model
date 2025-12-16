"""Timestamp utilities for the machine data model.

This module provides a centralized, configurable timestamp provider that can be
used throughout the codebase. It supports nanosecond precision timestamps and
allows customization for testing or alternative time sources.
"""

from collections.abc import Callable
import time


def _default_timestamp_ns() -> int:
    """Return the current time as nanoseconds since the Unix epoch.

    Returns:
        int:
            Nanoseconds since January 1, 1970 (UTC).

    """
    return time.time_ns()


# Default timestamp provider function
_timestamp_provider: Callable[[], int] = _default_timestamp_ns


def set_timestamp_provider(provider: Callable[[], int]) -> None:
    """Set a custom timestamp provider function.

    This allows users to customize how timestamps are generated, which is useful
    for testing or for using different time sources.

    Args:
        provider (Callable[[], int]):
            A callable that takes no arguments and returns an integer
            representing nanoseconds since the Unix epoch.

    Example:
        # Fixed timestamp
        >>> set_timestamp_provider(lambda: 1672531200000000000)

    """
    global _timestamp_provider
    _timestamp_provider = provider


def get_timestamp_provider() -> Callable[[], int]:
    """Get the current timestamp provider function.

    Returns:
        Callable[[], int]:
            The current timestamp provider function.

    """
    return _timestamp_provider


def reset_timestamp_provider() -> None:
    """Reset the timestamp provider to the default (time.time_ns())."""
    global _timestamp_provider
    _timestamp_provider = _default_timestamp_ns


def get_timestamp_ns() -> int:
    """Get the current timestamp using the configured provider.

    Returns:
        int:
            Nanoseconds since the Unix epoch.

    """
    return _timestamp_provider()
