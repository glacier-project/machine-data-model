"""Shared YAML construction helpers for connector subpackages."""

from collections.abc import Hashable
from typing import Any


def build_kwargs(
    data: dict[Hashable, Any], default_kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Build kwargs by merging data with defaults; reject unexpected keys.

    Args:
        data:
            Input data from YAML (typically the result of
            `loader.construct_mapping(node, deep=True)`).
        default_kwargs:
            Default values for all allowed keys. Any key in ``data`` that
            is not present here is rejected.

    Returns:
        The merged kwargs dictionary, ready to splat into a class
        constructor.

    Raises:
        ValueError: If ``data`` contains keys not present in
            ``default_kwargs``.
    """
    unexpected_keys = set(data.keys()) - set(default_kwargs.keys())
    if unexpected_keys:
        raise ValueError(
            f"Unexpected keys: {', '.join(map(str, unexpected_keys))}. "
            f"Allowed keys: {', '.join(default_kwargs.keys())}"
        )
    kwargs = default_kwargs.copy()
    for key, value in data.items():
        kwargs[str(key)] = value
    return kwargs
