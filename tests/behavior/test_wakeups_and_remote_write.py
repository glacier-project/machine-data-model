"""Tests for lost wakeups, duplicate subscriptions and the remote write fix."""

import logging
from typing import Any
from unittest.mock import MagicMock
import uuid
import warnings

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
    """The cache holds the base unit value: never infer success from it."""

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


class TestCachedReadsDoNotDrift:
    def test_cached_reads_of_a_non_base_unit_variable_are_stable(self) -> None:
        variable = remote_unit_variable(LengthUnits.Millimeter, 1, True)

        reads = [variable.read(force_remote_read=False) for _ in range(5)]

        assert reads == [pytest.approx(0.001)] * 5
        assert variable._read_internal_value() == pytest.approx(0.001)

    def test_forced_read_returns_raw_and_leaves_the_cache_correct(self) -> None:
        variable = remote_unit_variable(LengthUnits.Millimeter, 1, True)
        variable._connector.read_node_value.return_value = 5  # type: ignore[union-attr]

        forced = variable.read(force_remote_read=True)
        cached = [variable.read(force_remote_read=False) for _ in range(3)]

        # A forced read returns the connector value as it always did (unit of
        # the variable, issue #67); the cache holds the converted value.
        assert forced == 5
        assert variable._read_internal_value() == pytest.approx(0.005)
        assert cached == [pytest.approx(0.005)] * 3

    def test_forced_read_without_a_value_keeps_the_cache(self) -> None:
        variable = remote_unit_variable(LengthUnits.Millimeter, 1, True)
        variable._connector.read_node_value.return_value = None  # type: ignore[union-attr]

        forced = [variable.read(force_remote_read=True) for _ in range(3)]

        assert forced == [pytest.approx(0.001)] * 3

    def test_base_unit_variable_unchanged(self) -> None:
        variable, connector = remote_variable(True, value=1)
        connector.read_node_value.return_value = 7

        assert variable.read(force_remote_read=True) == 7
        assert variable.read(force_remote_read=False) == 7

    def test_string_and_bool_forced_reads(self) -> None:
        text = StringVariableNode(name="s", value="a", connector_name="c")
        flag = BooleanVariableNode(name="b", value=True, connector_name="c")
        for variable, raw in ((text, "z"), (flag, False)):
            connector = MagicMock()
            connector.read_node_value.return_value = raw
            variable.set_connector(connector)
            variable._remote_resource = RemoteResource("ns=1")

            assert variable.read(force_remote_read=True) == raw
            assert variable.read(force_remote_read=False) == raw

    def test_remote_object_refreshes_properties_without_drift(self) -> None:
        length = remote_unit_variable(LengthUnits.Millimeter, 1, True)
        length._name = "len"
        obj = ObjectVariableNode(
            name="o", properties={"len": length}, connector_name="c"
        )
        obj.set_connector(MagicMock())
        obj._remote_resource = RemoteResource("ns=1")
        length._connector.read_node_value.return_value = 5  # type: ignore[union-attr]

        forced = obj.read(force_remote_read=True)
        cached = [obj.read(force_remote_read=False) for _ in range(3)]

        assert forced == {"len": 5}
        assert length._read_internal_value() == pytest.approx(0.005)
        assert cached == [{"len": pytest.approx(0.005)}] * 3


def sent_values(variable: VariableNode) -> list[Any]:
    connector = variable._connector
    assert isinstance(connector, MagicMock)
    return [c.args[1] for c in connector.write_node_value.call_args_list]


class TestSnapshotRestore:
    @pytest.mark.parametrize(
        "unit, initial, base",
        [
            (LengthUnits.Millimeter, 1, 0.001),
            (TemperatureUnits.DegreeCelsius, 25, 298.15),
        ],
    )
    def test_remote_restore_sends_the_original_magnitude(
        self, unit: Any, initial: float, base: float
    ) -> None:
        variable = remote_unit_variable(unit, initial, True)
        original = variable._value
        variable.set_post_update_value_callback(lambda prev, curr: False)

        assert variable.write(initial + 4) is False

        sent = sent_values(variable)
        # The new value, then the original one in the unit of the variable.
        assert sent == [initial + 4, pytest.approx(initial)]
        assert variable._read_internal_value() == pytest.approx(base)
        assert variable._value is original

    @pytest.mark.parametrize(
        "unit, initial, base",
        [
            (LengthUnits.Millimeter, 1, 0.001),
            (TemperatureUnits.DegreeCelsius, 25, 298.15),
        ],
    )
    def test_local_restore_is_exact_for_non_base_units(
        self, unit: Any, initial: float, base: float
    ) -> None:
        variable = NumericalVariableNode(
            name="v", value=initial, measure_unit=unit
        )
        original = variable._value
        variable.set_post_update_value_callback(lambda prev, curr: False)

        assert variable.write(initial + 4) is False

        assert variable._read_internal_value() == pytest.approx(base)
        assert variable._value is original

    def test_restore_for_a_variable_without_unit(self) -> None:
        variable, connector = remote_variable(True, value=3)
        variable.set_post_update_value_callback(lambda prev, curr: False)

        assert variable.write(9) is False

        sent = [c.args[1] for c in connector.write_node_value.call_args_list]
        assert sent == [9, 3]
        assert variable._read_internal_value() == 3

    def test_object_restore_uses_each_property_unit(self) -> None:
        unit = LengthUnits.Millimeter
        length = remote_unit_variable(unit, 2, True)
        length._name = "len"
        flag = BooleanVariableNode(name="flag", value=True)
        flag_connector = MagicMock()
        flag_connector.write_node_value.return_value = True
        flag.set_connector(flag_connector)
        flag._remote_resource = RemoteResource("ns=2")
        obj = ObjectVariableNode(
            name="o",
            properties={"len": length, "flag": flag},
            connector_name="c",
        )
        obj.set_connector(MagicMock())
        obj._remote_resource = RemoteResource("ns=1")
        original = length._value
        obj.set_post_update_value_callback(lambda prev, curr: False)

        assert obj.write({"len": 0.5, "flag": False}) is False

        sent = sent_values(length)
        # The constructor of the object already converted its property once
        # (unit semantics, issue #67): the machine must get back whatever the
        # property held before the write, in the unit of the property.
        assert sent == [0.5, pytest.approx(original.convert(unit))]
        assert length._value is original
        assert flag._read_internal_value() is True
        flag_sent = [
            c.args[1] for c in flag_connector.write_node_value.call_args_list
        ]
        assert flag_sent == [False, True]


def object_with_properties(
    outcomes: dict[str, list[Any]],
) -> tuple[ObjectVariableNode, list[tuple[str, Any]]]:
    """Build a remote object; every property write is logged in order.

    `outcomes` gives, per property, the results of its successive remote
    writes: a bool, or an exception instance to raise.
    """
    log: list[tuple[str, Any]] = []
    properties: dict[str, VariableNode] = {}
    for name, results in outcomes.items():
        variable = NumericalVariableNode(name=name, value=1)
        pending = list(results)

        def write(
            resource: Any, value: Any, name: str = name, pending: list = pending
        ) -> bool:
            log.append((name, value))
            result = pending.pop(0) if pending else True
            if isinstance(result, Exception):
                raise result
            return bool(result)

        connector = MagicMock()
        connector.write_node_value.side_effect = write
        variable.set_connector(connector)
        variable._remote_resource = RemoteResource(f"ns={name}")
        properties[name] = variable
    obj = ObjectVariableNode(
        name="o", properties=properties, connector_name="c"
    )
    obj.set_connector(MagicMock())
    obj._remote_resource = RemoteResource("ns=o")
    return obj, log


class TestObjectWriteRollback:
    def test_first_property_fails_one_write_no_rollback(self) -> None:
        obj, log = object_with_properties(
            {"a": [False], "b": [True], "c": [True]}
        )

        assert obj.write({"a": 5, "b": 6, "c": 7}) is False

        assert log == [("a", 5)]
        assert obj.read(force_remote_read=False) == {"a": 1, "b": 1, "c": 1}

    def test_second_property_fails_exactly_one_rollback(self) -> None:
        obj, log = object_with_properties(
            {"a": [True, True], "b": [False], "c": [True]}
        )

        assert obj.write({"a": 5, "b": 6, "c": 7}) is False

        assert log == [("a", 5), ("b", 6), ("a", 1)]
        assert obj.read(force_remote_read=False) == {"a": 1, "b": 1, "c": 1}

    def test_rollback_is_in_reverse_order_and_only_confirmed(self) -> None:
        obj, log = object_with_properties(
            {"a": [True, True], "b": [True, True], "c": [False]}
        )

        assert obj.write({"a": 5, "b": 6, "c": 7}) is False

        assert log == [("a", 5), ("b", 6), ("c", 7), ("b", 1), ("a", 1)]

    def test_failed_rollback_is_logged_with_the_names(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        obj, log = object_with_properties(
            {"a": [True, False], "b": [True, True], "c": [False]}
        )

        with caplog.at_level(logging.ERROR):
            assert obj.write({"a": 5, "b": 6, "c": 7}) is False

        assert log == [("a", 5), ("b", 6), ("c", 7), ("b", 1), ("a", 1)]
        assert "Failed to roll back properties ['a']" in caplog.text

    def test_exception_rolls_back_confirmed_and_reraises(self) -> None:
        obj, log = object_with_properties(
            {"a": [True, True], "b": [RuntimeError("down")], "c": [True]}
        )

        with pytest.raises(RuntimeError, match="down"):
            obj.write({"a": 5, "b": 6, "c": 7})

        assert log == [("a", 5), ("b", 6), ("a", 1)]
        assert obj.read(force_remote_read=False) == {"a": 1, "b": 1, "c": 1}

    def test_exception_in_rollback_is_logged_and_the_rest_continues(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        obj, log = object_with_properties(
            {
                "a": [True, True],
                "b": [True, RuntimeError("rollback down")],
                "c": [False],
            }
        )

        with caplog.at_level(logging.ERROR):
            assert obj.write({"a": 5, "b": 6, "c": 7}) is False

        assert log == [("a", 5), ("b", 6), ("c", 7), ("b", 1), ("a", 1)]
        assert "Failed to roll back properties ['b']" in caplog.text

    @pytest.mark.parametrize(
        "value",
        [{"a": 5, "b": 6}, {"a": 5, "b": 6, "c": 7, "d": 8}, {}],
    )
    def test_missing_or_unknown_property_touches_nothing(
        self, value: dict[str, Any]
    ) -> None:
        obj, log = object_with_properties(
            {"a": [True], "b": [True], "c": [True]}
        )

        with pytest.raises(ValueError, match="missing properties"):
            obj.write(value)

        assert log == []
        assert obj.read(force_remote_read=False) == {"a": 1, "b": 1, "c": 1}

    def test_success_writes_each_property_once(self) -> None:
        obj, log = object_with_properties(
            {"a": [True], "b": [True], "c": [True]}
        )

        assert obj.write({"a": 5, "b": 6, "c": 7}) is True

        assert log == [("a", 5), ("b", 6), ("c", 7)]
        assert obj.read(force_remote_read=False) == {"a": 5, "b": 6, "c": 7}


class TestRemovedHookGuard:
    @pytest.mark.parametrize(
        "hook, advice",
        [
            ("_update_remote_value", "_write_remote(value) -> bool"),
            ("_update_value", "_write_remote(value) -> bool"),
            ("_read_remote_value", "_fetch_remote_value()"),
        ],
    )
    def test_overriding_a_removed_hook_warns(
        self, hook: str, advice: str
    ) -> None:
        with pytest.warns(DeprecationWarning, match=hook) as record:
            type(
                "LegacyVariable",
                (NumericalVariableNode,),
                {hook: lambda self, *args, **kwargs: None},
            )

        assert advice in str(record[0].message)
        assert "LegacyVariable" in str(record[0].message)

    def test_warning_points_at_the_subclass_definition(self) -> None:
        with pytest.warns(DeprecationWarning) as record:

            class Legacy(NumericalVariableNode):
                def _update_remote_value(self, value: Any) -> Any:
                    return value

        assert record[0].filename == __file__

    def test_only_the_defining_class_warns(self) -> None:
        with pytest.warns(DeprecationWarning):

            class Legacy(NumericalVariableNode):
                def _update_value(self, value: Any) -> Any:
                    return value

        with warnings.catch_warnings():
            warnings.simplefilter("error")

            class Child(Legacy):
                pass

    def test_regular_subclasses_do_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")

            class Regular(NumericalVariableNode):
                def _write_remote(self, value: Any) -> bool:
                    return True

                def _snapshot(self) -> Any:
                    return super()._snapshot()


class TestOffsetUnitRestore:
    @pytest.mark.parametrize(
        "unit, initial",
        [
            (TemperatureUnits.DegreeCelsius, 20.1),
            (TemperatureUnits.DegreeFahrenheit, 68.18),
            (TemperatureUnits.DegreeCelsius, 0.1),
            (LengthUnits.Millimeter, 3.3),
        ],
    )
    def test_restore_sends_exactly_the_original(
        self, unit: Any, initial: float
    ) -> None:
        variable = remote_unit_variable(unit, initial, True)
        original = variable._value
        variable.set_post_update_value_callback(lambda prev, curr: False)

        assert variable.write(initial + 5) is False

        # Exactly, not approximately: converting the measure back would pick
        # up noise (20.1 C -> 20.100000000000023).
        assert sent_values(variable) == [initial + 5, initial]
        assert variable._value is original

    def test_raw_value_follows_updates_and_internal_writes(self) -> None:
        variable = NumericalVariableNode(
            name="v", value=20.1, measure_unit=TemperatureUnits.DegreeCelsius
        )
        assert variable._remote_value(variable._snapshot()) == 20.1

        variable._update_internal_value(21.3)

        assert variable._remote_value(variable._snapshot()) == 21.3

    def test_noise_exists_without_the_raw_value(self) -> None:
        # Documents why the raw value is kept: the converted measure is not
        # an exact round trip for offset units.
        variable = NumericalVariableNode(
            name="v", value=20.1, measure_unit=TemperatureUnits.DegreeCelsius
        )

        converted = variable._value.convert(TemperatureUnits.DegreeCelsius)

        assert converted != 20.1
        assert variable._remote_value(variable._snapshot()) == 20.1
