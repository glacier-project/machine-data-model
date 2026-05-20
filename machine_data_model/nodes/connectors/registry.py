"""Central plugin registry for connector subpackages.

Each connector subpackage (e.g., `opcua`, `mqtt`) self-registers on
import by calling `register_connector` (deps installed) or
`register_unavailable` (deps missing). The builder and dumper consume
the registry to wire PyYAML constructors and representers without
naming specific connector classes.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import importlib
import pkgutil
from typing import Any

import yaml


@dataclass(frozen=True)
class ConnectorPlugin:
    """A connector whose optional deps are installed."""

    name: str
    connector_cls: type
    spec_cls: type
    construct_connector: Callable[[yaml.SafeLoader, yaml.MappingNode], Any]
    construct_spec: Callable[[yaml.SafeLoader, yaml.MappingNode], Any]
    represent_connector: Callable[[yaml.Dumper, Any], yaml.nodes.MappingNode]
    represent_spec: Callable[[yaml.Dumper, Any], yaml.nodes.MappingNode]


@dataclass(frozen=True)
class UnavailableConnector:
    """A connector known by name but whose optional deps are missing."""

    name: str
    yaml_tag_classes: tuple[str, ...]
    install_hint: str


_AVAILABLE: dict[str, ConnectorPlugin] = {}
_UNAVAILABLE: dict[str, UnavailableConnector] = {}
_DISCOVERED: bool = False


def register_connector(plugin: ConnectorPlugin) -> None:
    """Register an available connector. First registration wins."""
    _AVAILABLE.setdefault(plugin.name, plugin)


def register_unavailable(info: UnavailableConnector) -> None:
    """Register a known-but-unavailable connector. First registration wins."""
    _UNAVAILABLE.setdefault(info.name, info)


def iter_available() -> Iterable[ConnectorPlugin]:
    """Yield all registered available connector plugins."""
    return list(_AVAILABLE.values())


def iter_unavailable() -> Iterable[UnavailableConnector]:
    """Yield all registered unavailable connectors."""
    return list(_UNAVAILABLE.values())


def discover_connectors() -> None:
    """Import every subpackage of `machine_data_model.nodes.connectors`.

    Each subpackage's `__init__.py` is responsible for self-registering
    via `register_connector` or `register_unavailable`. Idempotent.
    """
    global _DISCOVERED
    if _DISCOVERED:
        return
    import machine_data_model.nodes.connectors as pkg

    for module_info in pkgutil.iter_modules(pkg.__path__):
        if not module_info.ispkg:
            continue
        importlib.import_module(f"{pkg.__name__}.{module_info.name}")
    _DISCOVERED = True


def _reset_for_testing() -> None:
    """Test-only: clear all registry state."""
    global _DISCOVERED
    _AVAILABLE.clear()
    _UNAVAILABLE.clear()
    _DISCOVERED = False
