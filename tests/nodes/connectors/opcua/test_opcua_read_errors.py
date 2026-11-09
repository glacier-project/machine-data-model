"""Read failures of the OPC UA connector surface as builtin exception types.

These tests use fakes and mocks only: no OPC UA server is involved. They check
the boundary the conditions rely on: a lost connection or a timeout is a
`ConnectionError` / `TimeoutError`, a wrong node stays a `ValueError`.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from asyncua.ua import uaerrors
import pytest

from machine_data_model.behavior.condition import (
    Condition,
    ConditionResult,
    WaitConditionOperator,
)
from machine_data_model.nodes.connectors.opcua import OpcuaConnector
from machine_data_model.nodes.connectors.opcua.opcua_connector import (
    _CONNECTION_STATUS_ERRORS,
    _CONNECTION_STATUS_NAMES,
    _TIMEOUT_STATUS_ERRORS,
    _TIMEOUT_STATUS_NAMES,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.variable_node import NumericalVariableNode


@pytest.fixture
def connector() -> Iterator[OpcuaConnector]:
    connector = OpcuaConnector(name="opc", ip="127.0.0.1", port=4840)
    yield connector
    connector._stop_owned_event_loop()


def with_node(connector: OpcuaConnector, node: Any) -> None:
    connector.client = MagicMock()
    connector._remote_node = AsyncMock(return_value=node)  # type: ignore[method-assign]


def failing_node(error: Exception) -> MagicMock:
    node = MagicMock()
    node.get_value = AsyncMock(side_effect=error)
    return node


RESOURCE = RemoteResource("ns=2;s=var")


class TestStatusCodeTables:
    @pytest.mark.parametrize(
        "name", _CONNECTION_STATUS_NAMES + _TIMEOUT_STATUS_NAMES
    )
    def test_every_listed_name_exists_in_asyncua(self, name: str) -> None:
        assert issubclass(getattr(uaerrors, name), uaerrors.UaError)

    def test_tables_keep_every_name(self) -> None:
        assert len(_CONNECTION_STATUS_ERRORS) == len(_CONNECTION_STATUS_NAMES)
        assert len(_TIMEOUT_STATUS_ERRORS) == len(_TIMEOUT_STATUS_NAMES)

    def test_the_two_tables_do_not_overlap(self) -> None:
        assert not set(_CONNECTION_STATUS_NAMES) & set(_TIMEOUT_STATUS_NAMES)

    @pytest.mark.parametrize(
        "name",
        [
            "BadSessionIdInvalid",
            "BadSessionNotActivated",
            "BadSecureChannelIdInvalid",
            "BadShutdown",
            "BadDisconnect",
            "BadConnectionRejected",
            "BadServerTooBusy",
            "BadTcpServerTooBusy",
            "BadTooManySessions",
            "BadResourceUnavailable",
            "BadOutOfService",
        ],
    )
    def test_review_listed_codes_are_connection_errors(self, name: str) -> None:
        assert name in _CONNECTION_STATUS_NAMES

    @pytest.mark.parametrize("name", ["BadNodeIdUnknown", "BadNoMatch"])
    def test_node_errors_are_not_in_the_tables(self, name: str) -> None:
        assert name not in _CONNECTION_STATUS_NAMES + _TIMEOUT_STATUS_NAMES


class TestReadErrors:
    @pytest.mark.parametrize("name", _CONNECTION_STATUS_NAMES)
    def test_lost_connection_is_a_connection_error(
        self, connector: OpcuaConnector, name: str
    ) -> None:
        with_node(connector, failing_node(getattr(uaerrors, name)()))

        with pytest.raises(ConnectionError) as info:
            connector.read_node_value(RESOURCE)

        assert isinstance(info.value.__cause__, uaerrors.UaError)

    @pytest.mark.parametrize("name", _TIMEOUT_STATUS_NAMES)
    def test_timeout_status_is_a_timeout_error(
        self, connector: OpcuaConnector, name: str
    ) -> None:
        with_node(connector, failing_node(getattr(uaerrors, name)()))

        with pytest.raises(TimeoutError):
            connector.read_node_value(RESOURCE)

    def test_builtin_connection_errors_pass_through(
        self, connector: OpcuaConnector
    ) -> None:
        with_node(connector, failing_node(ConnectionResetError("reset")))

        with pytest.raises(ConnectionError):
            connector.read_node_value(RESOURCE)

    def test_wrong_node_stays_a_value_error(
        self, connector: OpcuaConnector
    ) -> None:
        with_node(connector, failing_node(uaerrors.BadNodeIdUnknown()))

        with pytest.raises(ValueError, match="does not exist"):
            connector.read_node_value(RESOURCE)

    def test_client_not_connected_is_a_connection_error(
        self, connector: OpcuaConnector
    ) -> None:
        assert connector.client is None

        with pytest.raises(ConnectionError, match="not connected"):
            connector.read_node_value(RESOURCE)

    def test_successful_read_returns_the_value(
        self, connector: OpcuaConnector
    ) -> None:
        node = MagicMock()
        node.get_value = AsyncMock(return_value=42)
        with_node(connector, node)

        assert connector.read_node_value(RESOURCE) == 42


class TestConditionOnTopOfTheConnector:
    def variable(self, connector: OpcuaConnector) -> NumericalVariableNode:
        variable = NumericalVariableNode(
            name="v", value=1, connector_name="opc"
        )
        variable.set_connector(connector)
        variable.set_remote_path("ns=2;s=var")
        variable.configure_remote_resource()
        return variable

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (uaerrors.BadConnectionClosed(), ConditionResult.NO_DATA),
            (uaerrors.BadTimeout(), ConditionResult.NO_DATA),
        ],
    )
    def test_forced_read_failure_is_no_data(
        self,
        connector: OpcuaConnector,
        error: Exception,
        expected: ConditionResult,
    ) -> None:
        with_node(connector, failing_node(error))
        variable = self.variable(connector)
        cond = Condition("v", WaitConditionOperator.EQ, 1)

        outcome = cond.evaluate_on(variable, 1, force_remote_read=True)

        assert outcome.result is expected
        assert "read failed" in outcome.message

    def test_wrong_node_is_not_hidden_as_no_data(
        self, connector: OpcuaConnector
    ) -> None:
        with_node(connector, failing_node(uaerrors.BadNodeIdUnknown()))
        variable = self.variable(connector)
        cond = Condition("v", WaitConditionOperator.EQ, 1)

        with pytest.raises(ValueError, match="does not exist"):
            cond.evaluate_on(variable, 1, force_remote_read=True)


class TestNodeResolution:
    def resolver(self, connector: OpcuaConnector, error: Exception) -> None:
        client = MagicMock()
        client.get_root_node.return_value.get_child = AsyncMock(
            side_effect=error
        )
        connector.client = client

    def test_connection_loss_while_resolving_is_a_connection_error(
        self, connector: OpcuaConnector
    ) -> None:
        self.resolver(connector, uaerrors.BadConnectionClosed())

        with pytest.raises(ConnectionError):
            connector.read_node_value(RESOURCE)

    def test_unknown_path_stays_a_value_error(
        self, connector: OpcuaConnector
    ) -> None:
        self.resolver(connector, uaerrors.BadNoMatch())

        with pytest.raises(ValueError, match="doesn't exist"):
            connector.read_node_value(RESOURCE)


class TestClosedConnector:
    """Reading through a connector that was shut down (mocks only)."""

    def closed(self, connector: OpcuaConnector) -> None:
        connector._stop_owned_event_loop()
        assert connector._event_loop.is_closed()

    def test_read_is_a_connection_error(
        self, connector: OpcuaConnector
    ) -> None:
        self.closed(connector)

        with pytest.raises(ConnectionError, match="closed") as info:
            connector.read_node_value(RESOURCE)

        assert isinstance(info.value.__cause__, RuntimeError)

    def test_write_keeps_raising_runtime_error(
        self, connector: OpcuaConnector
    ) -> None:
        self.closed(connector)

        with pytest.raises(RuntimeError, match="event loop is closed"):
            connector.write_node_value(RESOURCE, 1)

    def test_other_runtime_errors_on_a_live_loop_propagate(
        self, connector: OpcuaConnector
    ) -> None:
        node = MagicMock()
        node.get_value = AsyncMock(side_effect=RuntimeError("bug"))
        with_node(connector, node)

        with pytest.raises(RuntimeError, match="bug"):
            connector.read_node_value(RESOURCE)

    def test_condition_sees_no_data_for_a_closed_connector(
        self, connector: OpcuaConnector
    ) -> None:
        variable = NumericalVariableNode(
            name="v", value=1, connector_name="opc"
        )
        variable.set_connector(connector)
        variable.set_remote_path("ns=2;s=var")
        variable.configure_remote_resource()
        self.closed(connector)

        outcome = Condition("v", WaitConditionOperator.EQ, 1).evaluate_on(
            variable, 1, force_remote_read=True
        )

        assert outcome.result is ConditionResult.NO_DATA
        assert "read failed (ConnectionError)" in outcome.message
