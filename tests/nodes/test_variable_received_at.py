"""`received_at` and `has_received_value` of variable nodes."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.folder_node import FolderNode
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


class TestDataModelWiring:
    """How a real `DataModel` wires the properties of a remote object."""

    def test_property_inherits_connector_and_is_remote(self) -> None:
        from machine_data_model.data_model import DataModel

        connector = MagicMock()
        connector.name = "c"
        connector.connect.return_value = True
        connector.read_node_value.return_value = None
        obj = ObjectVariableNode(
            name="obj",
            properties={"prop": NumericalVariableNode(name="prop", value=0)},
            connector_name="c",
        )
        root = FolderNode(name="root")
        root.add_child(obj)
        DataModel(name="dm", root=root, connectors=[connector])

        prop = obj._properties["prop"]
        assert prop.is_remote()
        assert prop.has_connector()
        # Each property subscribes on its own; the object does not.
        assert connector.subscribe_to_node_changes.call_count == 1
        assert not prop.has_received_value()
        assert not obj.has_received_value()

        prop._remote_subscription_callback(5, MagicMock())

        assert prop.has_received_value()
        assert obj.has_received_value()


class TestWalkUp:
    def test_local_property_follows_the_remote_object(self) -> None:
        prop = NumericalVariableNode(name="prop", value=0)
        obj = ObjectVariableNode(
            name="obj", properties={"prop": prop}, connector_name="c"
        )

        assert not prop.has_received_value()

        obj._mark_received()

        assert prop.has_received_value()
        assert obj.has_received_value()

    def test_local_variable_outside_any_remote_object(self) -> None:
        prop = NumericalVariableNode(name="prop", value=0)
        ObjectVariableNode(name="obj", properties={"prop": prop})

        assert prop.has_received_value()


class TestLocalObjectWithRemoteProperties:
    @staticmethod
    def build() -> tuple[ObjectVariableNode, NumericalVariableNode]:
        remote_prop = NumericalVariableNode(
            name="r", value=0, connector_name="c"
        )
        remote_prop.set_connector(MagicMock())
        obj = ObjectVariableNode(
            name="o",
            properties={
                "r": remote_prop,
                "l": NumericalVariableNode(name="l", value=1),
            },
        )
        return obj, remote_prop

    def test_unreceived_remote_property_makes_the_object_unreceived(
        self,
    ) -> None:
        obj, remote_prop = self.build()

        assert not obj.is_remote()
        assert not obj.has_received_value()

        remote_prop._remote_subscription_callback(3, MagicMock())

        assert obj.has_received_value()

    def test_nested_local_object_follows_its_remote_property(self) -> None:
        inner, remote_prop = self.build()
        outer = ObjectVariableNode(name="outer", properties={"inner": inner})

        assert not outer.has_received_value()

        remote_prop._mark_received()

        assert outer.has_received_value()

    def test_condition_on_such_an_object_is_no_data(self) -> None:
        from machine_data_model.behavior.condition import (
            Condition,
            ConditionResult,
            WaitConditionOperator,
        )

        obj, remote_prop = self.build()
        cond = Condition("o", WaitConditionOperator.EQ, {"r": 0, "l": 1})

        before = cond.evaluate(lambda path: obj, None)
        remote_prop._mark_received()
        after = cond.evaluate(lambda path: obj, None)

        assert before.result is ConditionResult.NO_DATA
        assert after.result is ConditionResult.OK


class TestObjectUpdateValidation:
    @staticmethod
    def build() -> ObjectVariableNode:
        return ObjectVariableNode(
            name="o",
            properties={
                "a": NumericalVariableNode(name="a", value=1),
                "b": NumericalVariableNode(name="b", value=2),
            },
        )

    def test_missing_property_raises_value_error(self) -> None:
        obj = self.build()

        with pytest.raises(ValueError, match="missing \\['b'\\]"):
            obj._update_internal_value({"a": 5})

        assert obj._read_internal_value() == {"a": 1, "b": 2}

    def test_unknown_property_raises_value_error(self) -> None:
        obj = self.build()

        with pytest.raises(ValueError, match="unknown \\['c'\\]"):
            obj._update_internal_value({"a": 5, "b": 6, "c": 7})

        assert obj._read_internal_value() == {"a": 1, "b": 2}

    def test_same_count_wrong_names_raises_value_error(self) -> None:
        obj = self.build()

        with pytest.raises(ValueError):
            obj._update_internal_value({"a": 5, "x": 6})

        assert obj._read_internal_value() == {"a": 1, "b": 2}

    def test_valid_value_updates_all_properties(self) -> None:
        obj = self.build()

        assert obj._update_internal_value({"a": 5, "b": 6}) == {"a": 5, "b": 6}

    def test_remote_message_with_wrong_shape_is_a_value_error(self) -> None:
        obj = self.build()

        with pytest.raises(ValueError):
            obj._remote_subscription_callback({"a": 5}, MagicMock())
