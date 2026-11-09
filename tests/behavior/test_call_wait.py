"""`on_unmet: wait` of `CallMethodNode`: attempt, subscribe, retry."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import execution_success
from machine_data_model.behavior.execution_error import ExecutionErrorCode
from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
    VariableNode,
)
from tests.behavior import StubNode, wait_for_nonzero

EQ = WaitConditionOperator.EQ
GE = WaitConditionOperator.GE


class Setup:
    """A parent that waits to call a callee guarded by two conditions."""

    def __init__(
        self,
        composite_callee: bool = False,
        requires: list[Condition] | None = None,
        on_unmet: str | None = "wait",
        mode: float = 1,
        level: float = 0,
        callee_parameters: list[Any] | None = None,
        call_kwargs: dict[str, Any] | None = None,
        parent_parameters: list[Any] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.callee_stub = StubNode(lambda: execution_success())
        self.after = StubNode(lambda: execution_success())
        self.woken: list[str] = []
        self.mode = NumericalVariableNode(id="mode", name="mode", value=mode)
        self.level = NumericalVariableNode(
            id="level", name="level", value=level
        )
        for variable in (self.mode, self.level):
            variable.set_subscription_callback(self.on_change)
        conditions = (
            requires
            if requires is not None
            else [Condition("mode", EQ, 2), Condition("level", GE, 1)]
        )
        self.callee: MethodNode
        if composite_callee:
            self.callee = CompositeMethodNode(
                id="callee",
                name="callee",
                parameters=callee_parameters,
                cfg=ControlFlow(nodes=[self.callee_stub]),
                requires=conditions,
            )
        else:
            self.callee = MethodNode(
                id="callee",
                name="callee",
                parameters=callee_parameters,
                returns=[NumericalVariableNode(id="r", name="r", value=0)],
                callback=self.record,
                requires=conditions,
            )
        self.call = CallMethodNode(
            method_node="callee",
            args=[],
            kwargs=call_kwargs or {},
            on_unmet=on_unmet,
        )
        self.call.set_ref_node(self.callee)
        self.parent = CompositeMethodNode(
            id="parent",
            name="parent",
            parameters=parent_parameters,
            cfg=ControlFlow(nodes=[self.call, self.after]),
        )
        self.data_model = DataModel(name="dm")
        for node in (self.mode, self.level, self.callee, self.parent):
            self.data_model.root.add_child(node)
        self.data_model._register_nodes(self.data_model.root)

    def on_change(self, subscription: Any, node: Any, value: Any) -> None:
        self.woken.append(subscription.subscriber_id)

    def record(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        return 0

    def callee_runs(self) -> int:
        return len(self.calls) + self.callee_stub.runs

    def start(self, **kwargs: Any) -> str:
        result = self.parent(**kwargs)
        assert result.error is None
        context_id = result.return_values["@context_id"]
        assert isinstance(context_id, str)
        return context_id

    def resume(self, context_id: str) -> Any:
        return self.parent.resume_execution(context_id)

    def subscribers(self, variable: VariableNode) -> list[str]:
        return [s.subscriber_id for s in variable.get_subscriptions()]

    def wait_keys(self, context_id: str) -> list[str]:
        context = self.parent._contexts.get(context_id)
        if context is None:
            return []
        return [
            key for key in context._locals if key.startswith("call_method_wait")
        ]


kinds = pytest.mark.parametrize("composite_callee", [False, True])


@kinds
class TestWaiting:
    def test_unmet_requires_keep_the_node_running(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee)

        context_id = setup.start()

        assert setup.callee_runs() == 0
        assert setup.after.runs == 0
        assert setup.parent._contexts[context_id].is_active()

    def test_subscribed_to_every_variable_of_every_condition(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, mode=2, level=0)

        context_id = setup.start()

        # `mode` already holds, `level` does not: both can flip the result.
        assert setup.subscribers(setup.mode) == [context_id]
        assert setup.subscribers(setup.level) == [context_id]

    def test_a_change_wakes_the_context_and_the_call_happens_once(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()

        setup.mode.write(2)
        assert setup.woken == [context_id]
        setup.level.write(1)
        result = setup.resume(context_id)

        assert result.error is None
        assert setup.callee_runs() == 1
        assert setup.after.runs == 1
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []
        assert setup.wait_keys(context_id) == []

    def test_stays_running_when_still_unmet(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()

        setup.mode.write(2)
        first = setup.resume(context_id)

        assert first.error is None
        assert setup.callee_runs() == 0
        assert setup.parent._contexts[context_id].is_active()
        # Still subscribed to both, once each.
        assert setup.subscribers(setup.mode) == [context_id]
        assert setup.subscribers(setup.level) == [context_id]

        setup.level.write(1)
        setup.resume(context_id)

        assert setup.callee_runs() == 1

    def test_a_condition_that_flips_back_before_the_retry_does_not_call(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        context_id = setup.start()

        setup.mode.write(2)
        setup.mode.write(1)
        setup.resume(context_id)

        # The retry looked at the value now, not at the one that woke it.
        assert setup.callee_runs() == 0
        assert setup.subscribers(setup.mode) == [context_id]

    def test_the_check_and_the_call_are_one_step(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        context_id = setup.start()
        setup.mode._update_internal_value(2)

        # No variable event arrived: the node is only resumed. The call
        # happens in the same step as the check that allowed it.
        setup.resume(context_id)

        assert setup.callee_runs() == 1

    def test_a_requires_that_hold_call_at_once_without_subscribing(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, mode=2, level=1)

        result = setup.parent()

        assert result.error is None
        assert setup.callee_runs() == 1
        assert setup.after.runs == 1
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []


@kinds
class TestRecheckAfterSubscribing:
    def test_a_change_between_the_check_and_the_subscription_is_seen(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        real = setup.callee._check_requires
        first = [True]

        def racing(kwargs: dict[str, Any]) -> None:
            try:
                real(kwargs)
            except Exception:
                if first:
                    first.clear()
                    # Another thread changes the value right after the check
                    # that rejected the call, before the node subscribed.
                    setup.mode._update_internal_value(2)
                raise

        setup.callee._check_requires = racing  # type: ignore[method-assign]

        result = setup.parent()

        # No wakeup was needed: the second look, after subscribing, passed.
        assert result.error is None
        assert setup.callee_runs() == 1
        assert setup.after.runs == 1
        assert setup.subscribers(setup.mode) == []


@kinds
class TestConcurrentContexts:
    def test_contexts_do_not_share_a_subscription(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])

        first = setup.start()
        second = setup.start()

        assert first != second
        assert sorted(setup.subscribers(setup.mode)) == sorted([first, second])
        subscriptions = setup.mode.get_subscriptions()
        assert subscriptions[0] is not subscriptions[1]

    def test_both_wake_and_each_calls_once(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        first = setup.start()
        second = setup.start()

        setup.mode.write(2)
        setup.resume(first)

        assert sorted(setup.woken) == sorted([first, second])
        assert setup.callee_runs() == 1
        # The other context keeps its own subscription.
        assert setup.subscribers(setup.mode) == [second]

        setup.resume(second)

        assert setup.callee_runs() == 2
        assert setup.subscribers(setup.mode) == []


class TestOtherModes:
    @pytest.mark.parametrize("composite_callee", [False, True])
    def test_fail_never_subscribes(self, composite_callee: bool) -> None:
        setup = Setup(composite_callee, on_unmet="fail")

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []

    def test_configuration_error_is_never_waited_on(self) -> None:
        setup = Setup(requires=[Condition("nope", EQ, 1)])

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert setup.callee_runs() == 0

    def test_a_configuration_error_after_waiting_fails_and_unsubscribes(
        self,
    ) -> None:
        setup = Setup()
        context_id = setup.start()
        assert setup.subscribers(setup.mode) == [context_id]
        # The callee is reconfigured with a condition that cannot be evaluated.
        setup.callee._requires = (Condition("nope", EQ, 1),)

        result = setup.resume(context_id)

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []

    def test_remote_variable_without_connector_is_not_waited_on(self) -> None:
        setup = Setup(requires=[Condition("remote", EQ, 1)])
        remote = NumericalVariableNode(
            id="remote", name="remote", value=1, connector_name="missing"
        )
        setup.data_model.root.add_child(remote)
        setup.data_model._register_nodes(setup.data_model.root)

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert remote.get_subscriptions() == []


class TestRemoteValueNeverReceived:
    def test_waits_for_the_first_value_and_then_calls(self) -> None:
        setup = Setup(requires=[Condition("remote", EQ, 5)])
        remote = NumericalVariableNode(
            id="remote", name="remote", value=5, connector_name="c"
        )
        remote.set_connector(MagicMock())
        remote.set_subscription_callback(setup.on_change)
        setup.data_model.root.add_child(remote)
        setup.data_model._register_nodes(setup.data_model.root)

        context_id = setup.start()
        # The default (5) would satisfy the condition, but nothing was
        # received: NO_DATA, so it waits.
        assert setup.callee_runs() == 0
        assert setup.subscribers(remote) == [context_id]

        remote._remote_subscription_callback(5, MagicMock())
        assert setup.woken == [context_id]
        setup.resume(context_id)

        assert setup.callee_runs() == 1
        assert setup.subscribers(remote) == []


class TestResubscription:
    def test_a_templated_path_that_changes_moves_the_subscription(
        self,
    ) -> None:
        setup = Setup(
            requires=[Condition("${which}", EQ, 2)],
            callee_parameters=[
                StringVariableNode(id="which", name="which", value="mode")
            ],
            call_kwargs={"which": "${w}"},
            parent_parameters=[
                StringVariableNode(id="w", name="w", value="mode")
            ],
        )
        context_id = setup.start()
        assert setup.subscribers(setup.mode) == [context_id]
        assert setup.subscribers(setup.level) == []

        setup.parent._contexts[context_id].set_value("w", "level")
        setup.resume(context_id)

        # The old variable is dropped before the new one is subscribed.
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == [context_id]

        setup.level.write(2)
        setup.resume(context_id)

        assert setup.callee_runs() == 1
        assert setup.subscribers(setup.level) == []


class TestCompositeCalleeThatPends:
    def test_a_started_callee_is_not_a_waiting_call(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        mode = NumericalVariableNode(id="mode", name="mode", value=2)
        callee = CompositeMethodNode(
            id="callee",
            name="callee",
            cfg=ControlFlow(nodes=[wait_for_nonzero(trigger)]),
            requires=[Condition("mode", EQ, 2)],
        )
        call = CallMethodNode(
            method_node="callee", args=[], kwargs={}, on_unmet="wait"
        )
        call.set_ref_node(callee)
        parent = CompositeMethodNode(
            id="parent", name="parent", cfg=ControlFlow(nodes=[call])
        )
        data_model = DataModel(name="dm")
        for node in (trigger, mode, callee, parent):
            data_model.root.add_child(node)
        data_model._register_nodes(data_model.root)

        result = parent()

        # The requires held: the callee started and waits on its own node.
        context_id = result.return_values["@context_id"]
        context = parent._contexts[context_id]
        assert not [
            k for k in context._locals if k.startswith("call_method_wait")
        ]
        assert mode.get_subscriptions() == []
