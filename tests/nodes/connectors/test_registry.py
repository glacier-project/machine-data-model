"""Tests for the connector plugin registry."""

from unittest.mock import patch

from machine_data_model.nodes.connectors.registry import (
    ConnectorPlugin,
    UnavailableConnector,
    _reset_for_testing,
    discover_connectors,
    iter_available,
    iter_unavailable,
    register_connector,
    register_unavailable,
)


def _make_plugin(name: str = "fake") -> ConnectorPlugin:
    class _FakeConnector: ...

    class _FakeSpec: ...

    return ConnectorPlugin(
        name=name,
        connector_cls=_FakeConnector,
        spec_cls=_FakeSpec,
        construct_connector=lambda loader, node: None,
        construct_spec=lambda loader, node: None,
        # pyrefly: ignore[bad-argument-type]
        represent_connector=lambda dumper, obj: None,
        # pyrefly: ignore[bad-argument-type]
        represent_spec=lambda dumper, obj: None,
    )


def setup_function() -> None:
    _reset_for_testing()


def test_register_connector_makes_it_available() -> None:
    plugin = _make_plugin("opcua")
    register_connector(plugin)
    assert list(iter_available()) == [plugin]
    assert list(iter_unavailable()) == []


def test_register_connector_is_idempotent() -> None:
    plugin = _make_plugin("opcua")
    register_connector(plugin)
    register_connector(plugin)
    assert list(iter_available()) == [plugin]


def test_re_registering_under_same_name_is_a_noop() -> None:
    first = _make_plugin("opcua")
    second = _make_plugin("opcua")
    register_connector(first)
    register_connector(second)
    available = list(iter_available())
    assert len(available) == 1
    assert available[0] is first  # first wins


def test_register_unavailable_makes_it_listed_as_unavailable() -> None:
    info = UnavailableConnector(
        name="opcua",
        yaml_tag_classes=("OpcuaConnector", "OpcuaRemoteResourceSpec"),
        install_hint="pip install machine-data-model[opcua]",
    )
    register_unavailable(info)
    assert list(iter_unavailable()) == [info]
    assert list(iter_available()) == []


def test_re_registering_unavailable_under_same_name_is_a_noop() -> None:
    first = UnavailableConnector(
        name="opcua",
        yaml_tag_classes=("OpcuaConnector",),
        install_hint="pip install machine-data-model[opcua]",
    )
    second = UnavailableConnector(
        name="opcua",
        yaml_tag_classes=("OpcuaConnector", "OpcuaRemoteResourceSpec"),
        install_hint="pip install something-else",
    )
    register_unavailable(first)
    register_unavailable(second)
    unavailable = list(iter_unavailable())
    assert len(unavailable) == 1
    assert unavailable[0] is first  # first wins


def test_discover_connectors_is_idempotent() -> None:
    with patch(
        "machine_data_model.nodes.connectors.registry.importlib.import_module"
    ) as mock_import:
        discover_connectors()
        first_call_count = mock_import.call_count
        assert first_call_count > 0  # imported at least one subpackage

        discover_connectors()
        # Second call must NOT import anything new — the _DISCOVERED guard
        # short-circuits.
        assert mock_import.call_count == first_call_count
