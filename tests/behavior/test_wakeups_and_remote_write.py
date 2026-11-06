"""Tests for lost wakeups, duplicate subscriptions and the remote write fix."""

import logging
from typing import Any
from unittest.mock import MagicMock
import uuid

import pytest
from unitsnet_py import LengthUnits, TemperatureUnits

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.local_execution_node import WaitConditionNode
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
    VariableNode,
)


def make_wait(variable: VariableNode, rhs: Any) -> WaitConditionNode:
    wait = WaitConditionNode(
        variable_node=variable.name, rhs=rhs, op=WaitConditionOperator.GE
    )
    wait.set_ref_node(variable)
    return wait


class TestNotifyIteratesOverACopy:
    def test_unsubscribing_in_callback_does_not_skip_waiters(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        woken: list[str] = []

        def callback(
            subscription: VariableSubscription, node: VariableNode, value: Any
        ) -> None:
            woken.append(subscription.subscriber_id)
            node.unsubscribe(subscription)

        for name in ("a", "b", "c"):
            variable.subscribe(
                VariableSubscription(name, subscription_callback=callback)
            )

        variable.write(1)

        assert woken == ["a", "b", "c"]
        assert variable.get_subscriptions() == []

    def test_three_waiters_one_write_all_resume(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        wait = make_wait(variable, 5)
        contexts = [ExecutionContext(str(uuid.uuid4())) for _ in range(3)]
        woken: list[str] = []

        def resume(
            subscription: VariableSubscription, node: VariableNode, value: Any
        ) -> None:
            woken.append(subscription.subscriber_id)
            for context in contexts:
                if context.id() == subscription.subscriber_id:
                    assert wait.execute(context).success

        for context in contexts:
            context.set_subscription_callback(resume)
            assert not wait.execute(context).success

        variable.write(5)

        assert sorted(woken) == sorted(c.id() for c in contexts)
        assert variable.get_subscriptions() == []


class TestSubscriptionPerContext:
    def test_second_subscription_of_a_context_is_adopted(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        wait = make_wait(variable, 5)
        context = ExecutionContext(str(uuid.uuid4()))
        woken: list[str] = []
        context.set_subscription_callback(
            lambda sub, node, value: woken.append(sub.subscriber_id)
        )
        assert not wait.execute(context).success
        first = variable.get_subscriptions()[0]
        # Simulate a lost context key: the node would create a second object.
        for key in [k for k in context.locals() if k.endswith("_subscription")]:
            context.delete_value(key)

        assert not wait.execute(context).success

        assert variable.get_subscriptions() == [first]
        variable.write(5)
        assert woken == [context.id()]
        assert wait.execute(context).success
        assert variable.get_subscriptions() == []

    def test_other_subscribers_keep_independent_subscriptions(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)

        assert variable.subscribe(VariableSubscription("client", "c1"))
        assert variable.subscribe(VariableSubscription("client", "c2"))

        assert len(variable.get_subscriptions()) == 2
        found = variable.find_subscription_by_subscriber("client")
        assert found is not None and found.correlation_id == "c1"
        assert variable.find_subscription_by_subscriber("nobody") is None


def remote_variable(
    write_result: bool | Exception, value: float = 1
) -> tuple[NumericalVariableNode, MagicMock]:
    variable = NumericalVariableNode(
        id="v", name="v", value=value, connector_name="c"
    )
    connector = MagicMock()
    connector.write_node_value.return_value = write_result
    connector.read_node_value.return_value = value
    variable.set_connector(connector)
    variable._remote_resource = RemoteResource("ns=1")
    return variable, connector


class TestRemoteWrite:
    def test_confirmed_write_updates_cache_and_notifies(self) -> None:
        variable, connector = remote_variable(True)
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        assert variable.write(5)

        assert variable.read(force_remote_read=False) == 5
        assert notified == [5]
        connector.write_node_value.assert_called_once()

    def test_failed_write_keeps_cache_and_does_not_notify(self) -> None:
        variable, connector = remote_variable(False)
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        assert variable.write(5) is False

        assert variable.read(force_remote_read=False) == 1
        assert notified == []

    def test_connector_exception_propagates_and_keeps_cache(self) -> None:
        variable, _ = remote_variable(RuntimeError("down"))
        variable._connector.write_node_value.side_effect = RuntimeError("down")  # type: ignore[union-attr]

        with pytest.raises(RuntimeError):
            variable.write(5)

        assert variable.read(force_remote_read=False) == 1

    def test_local_variable_unchanged(self) -> None:
        variable = NumericalVariableNode(name="v", value=1)
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        assert variable.write(5)

        assert variable.read() == 5
        assert notified == [5]

    def test_post_update_false_still_restores_previous_value(self) -> None:
        variable = StringVariableNode(name="s", value="a")
        variable.set_post_update_value_callback(lambda prev, curr: False)

        assert variable.write("b") is False

        assert variable.read() == "a"


def remote_unit_variable(
    unit: Any, value: float, write_result: bool
) -> NumericalVariableNode:
    variable = NumericalVariableNode(
        id="v", name="v", value=value, measure_unit=unit, connector_name="c"
    )
    connector = MagicMock()
    connector.write_node_value.return_value = write_result
    variable.set_connector(connector)
    variable._remote_resource = RemoteResource("ns=1")
    return variable


class TestRemoteWriteWithUnits:
    """The cache holds the base unit value: never infer success from it.

    The cache is inspected with `_read_internal_value`: `read(False)` on a
    remote variable with a non-base unit feeds the base value back through the
    unit conversion on every call (pre-existing bug, not covered here).
    """

    @pytest.mark.parametrize(
        "unit, written, base",
        [
            (LengthUnits.Millimeter, 5, 0.005),
            (TemperatureUnits.DegreeCelsius, 25, 298.15),
        ],
    )
    def test_confirmed_write_with_unit(
        self, unit: Any, written: float, base: float
    ) -> None:
        variable = remote_unit_variable(unit, 1, True)
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        assert variable.write(written) is True

        assert variable._read_internal_value() == pytest.approx(base)
        assert notified == [pytest.approx(base)]

    @pytest.mark.parametrize(
        "unit",
        [LengthUnits.Millimeter, TemperatureUnits.DegreeCelsius],
    )
    def test_failed_write_with_unit(self, unit: Any) -> None:
        variable = remote_unit_variable(unit, 1, False)
        before = variable._read_internal_value()
        # Bypass the cached read of `write()` (pre-existing unit drift bug) so
        # only the effect of the failed remote write is observed.
        variable._read_value = (  # type: ignore[method-assign]
            lambda force_remote_read=False: variable._read_internal_value()
        )
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        assert variable.write(5) is False

        assert variable._read_internal_value() == before
        assert notified == []


class TestRejectedRemoteUpdate:
    def test_restore_succeeds(self) -> None:
        variable, connector = remote_variable(True, value=1)
        variable.set_post_update_value_callback(lambda prev, curr: False)
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        assert variable.write(5) is False

        assert variable.read(force_remote_read=False) == 1
        assert notified == []
        # Write of the new value, then the restore of the previous one.
        assert connector.write_node_value.call_count == 2

    def test_restore_fails_keeps_what_the_machine_holds(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        variable, connector = remote_variable(True, value=1)
        connector.write_node_value.side_effect = [True, False]
        variable.set_post_update_value_callback(lambda prev, curr: False)
        notified: list[Any] = []
        variable.subscribe(
            VariableSubscription(
                "s", subscription_callback=lambda s, n, v: notified.append(v)
            )
        )

        with caplog.at_level(logging.ERROR):
            assert variable.write(5) is False

        # The machine holds the new value, so does the cache; no notification.
        assert variable.read(force_remote_read=False) == 5
        assert notified == []
        assert "Failed to restore" in caplog.text


class TestWaitNits:
    def test_adopted_subscription_gets_the_context_callback(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        wait = make_wait(variable, 5)
        context = ExecutionContext(str(uuid.uuid4()))
        assert not wait.execute(context).success
        first = variable.get_subscriptions()[0]
        callback_before = first.subscription_callback
        assert callback_before is None
        for key in [k for k in context.locals() if k.endswith("_subscription")]:
            context.delete_value(key)
        woken: list[str] = []
        context.set_subscription_callback(
            lambda sub, node, value: woken.append(sub.subscriber_id)
        )

        assert not wait.execute(context).success

        callback_after = first.subscription_callback
        assert callback_after is not None
        variable.write(5)
        assert woken == [context.id()]

    def test_release_deletes_keys_even_if_unsubscribe_fails(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        wait = make_wait(variable, 5)
        context = ExecutionContext(str(uuid.uuid4()))
        wait.execute(context)

        def boom(*args: Any, **kwargs: Any) -> bool:
            raise RuntimeError("unsubscribe failed")

        variable.unsubscribe = boom  # type: ignore[method-assign]

        with pytest.raises(RuntimeError):
            wait.release(context)

        assert not any(k.startswith("wait_") for k in context.locals())


class TestObjectRemoteWrite:
    def test_falsy_property_values_are_not_failures(self) -> None:
        def prop(variable: VariableNode) -> VariableNode:
            connector = MagicMock()
            connector.write_node_value.return_value = True
            variable.set_connector(connector)
            variable._remote_resource = RemoteResource("ns=1")
            return variable

        number = prop(NumericalVariableNode(name="n", value=1))
        flag = prop(BooleanVariableNode(name="b", value=True))
        text = prop(StringVariableNode(name="s", value="x"))
        obj = ObjectVariableNode(
            name="o",
            properties={"n": number, "b": flag, "s": text},
            connector_name="c",
        )
        connector = MagicMock()
        connector.write_node_value.return_value = True
        obj.set_connector(connector)
        obj._remote_resource = RemoteResource("ns=1")

        assert obj.write({"n": 0, "b": False, "s": ""}) is True

        assert obj.read(force_remote_read=False) == {
            "n": 0,
            "b": False,
            "s": "",
        }

    def test_failed_property_restores_written_ones_and_fails(self) -> None:
        first = NumericalVariableNode(name="a", value=1)
        second = NumericalVariableNode(name="b", value=2)
        connector_a = MagicMock()
        connector_a.write_node_value.return_value = True
        connector_b = MagicMock()
        connector_b.write_node_value.return_value = False
        for variable, connector in (
            (first, connector_a),
            (second, connector_b),
        ):
            variable.set_connector(connector)
            variable._remote_resource = RemoteResource("ns=1")
        obj = ObjectVariableNode(
            name="o", properties={"a": first, "b": second}, connector_name="c"
        )
        obj.set_connector(MagicMock())
        obj._remote_resource = RemoteResource("ns=1")

        assert obj.write({"a": 10, "b": 20}) is False

        assert obj.read(force_remote_read=False) == {"a": 1, "b": 2}
        # "a" was written, then restored.
        assert connector_a.write_node_value.call_count == 2
