"""`received_at` and `has_received_value` of variable nodes."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
    VariableNode,
)


def remote(node: VariableNode, read_value: Any = None) -> MagicMock:
    connector = MagicMock()
    connector.read_node_value.return_value = read_value
    connector.write_node_value.return_value = True
    node.set_connector(connector)
    node.set_remote_path("ns=1")
    node._remote_resource = RemoteResource("ns=1")
    return connector


def numeric(read_value: Any = None) -> tuple[NumericalVariableNode, MagicMock]:
    node = NumericalVariableNode(name="v", value=7, connector_name="c")
    return node, remote(node, read_value)


def make(kind: str) -> tuple[VariableNode, Any]:
    if kind == "numeric":
        return NumericalVariableNode(name="v", value=7, connector_name="c"), 9
    if kind == "string":
        return StringVariableNode(name="v", value="a", connector_name="c"), "b"
    return BooleanVariableNode(name="v", value=False, connector_name="c"), True


KINDS = ["numeric", "string", "boolean"]


class TestLocal:
    def test_local_variable_always_has_a_value(self) -> None:
        node = NumericalVariableNode(name="v", value=1)

        assert node.has_received_value()
        assert node.received_at is None

    def test_remote_variable_starts_without_a_value(self) -> None:
        node, _ = numeric()

        assert not node.has_received_value()
        assert node.received_at is None


@pytest.mark.parametrize("kind", KINDS)
class TestOriginSites:
    def test_initial_read_none_does_not_count(self, kind: str) -> None:
        node, _ = make(kind)
        remote(node, None)

        node.subscribe_to_remote_changes()

        assert not node.has_received_value()
        assert node.received_at is None

    def test_initial_read_with_value_counts(self, kind: str) -> None:
        node, value = make(kind)
        remote(node, value)

        node.subscribe_to_remote_changes()

        assert node.has_received_value()
        assert node.received_at is not None

    def test_subscription_callback_counts(self, kind: str) -> None:
        node, value = make(kind)
        remote(node, None)

        node._remote_subscription_callback(value, MagicMock())

        assert node.has_received_value()
        assert node.received_at is not None

    def test_forced_read_with_value_counts(self, kind: str) -> None:
        node, value = make(kind)
        remote(node, value)

        node.read(force_remote_read=True)

        assert node.has_received_value()

    def test_forced_read_with_none_does_not_count(self, kind: str) -> None:
        node, _ = make(kind)
        remote(node, None)

        node.read(force_remote_read=True)

        assert not node.has_received_value()

    def test_cached_read_of_the_default_does_not_count(self, kind: str) -> None:
        node, value = make(kind)
        remote(node, value)

        node.read(force_remote_read=False)
        node.read(force_remote_read=False)

        assert not node.has_received_value()
        assert node.received_at is None

    def test_confirmed_write_does_not_count(self, kind: str) -> None:
        node, value = make(kind)
        remote(node, None)

        assert node.write(value)

        assert not node.has_received_value()
        assert node.received_at is None


class TestTimestamp:
    def test_later_value_moves_the_timestamp_forward(self) -> None:
        node, _ = numeric()
        node._remote_subscription_callback(1, MagicMock())
        first = node.received_at
        assert first is not None

        node._remote_subscription_callback(2, MagicMock())

        assert node.received_at is not None
        assert node.received_at >= first

    def test_none_from_the_callback_does_not_count(self) -> None:
        node, _ = numeric()
        node._update_internal_value = MagicMock()  # type: ignore[method-assign]

        node._remote_subscription_callback(None, MagicMock())

        assert node.received_at is None


class TestObject:
    @staticmethod
    def build(connected: bool = True) -> ObjectVariableNode:
        obj = ObjectVariableNode(
            name="o",
            properties={
                "a": NumericalVariableNode(name="a", value=1),
                "b": StringVariableNode(name="b", value="x"),
            },
            connector_name="c",
        )
        if connected:
            remote(obj)
        return obj

    def test_starts_without_a_value(self) -> None:
        obj = self.build()

        assert not obj.has_received_value()
        assert obj.received_at is None

    def test_received_when_the_object_receives_a_value(self) -> None:
        obj = self.build()

        obj._remote_subscription_callback({"a": 2, "b": "y"}, MagicMock())

        assert obj.has_received_value()
        assert obj.received_at is not None

    def test_not_received_until_every_property_received(self) -> None:
        obj = self.build()

        obj._properties["a"]._mark_received()

        assert not obj.has_received_value()
        assert obj.received_at is None

        obj._properties["b"]._mark_received()

        assert obj.has_received_value()
        assert obj.received_at is not None

    def test_received_at_is_the_oldest_property(self) -> None:
        obj = self.build()
        obj._properties["a"]._received_at = 10.0
        obj._properties["b"]._received_at = 20.0

        assert obj.received_at == 10.0

    def test_local_object_always_has_a_value(self) -> None:
        obj = ObjectVariableNode(
            name="o", properties={"a": NumericalVariableNode(name="a")}
        )

        assert obj.has_received_value()

    def test_remote_object_without_properties_has_a_value(self) -> None:
        obj = ObjectVariableNode(name="o", connector_name="c")

        assert obj.has_received_value()
        assert obj.received_at is None

    def test_initial_read_marks_the_object(self) -> None:
        obj = self.build()
        obj.connector.read_node_value.return_value = {"a": 3, "b": "z"}  # type: ignore[union-attr]

        obj.subscribe_to_remote_changes()

        assert obj.has_received_value()
