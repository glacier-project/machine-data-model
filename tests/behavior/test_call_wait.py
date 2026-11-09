"""`on_unmet: wait` of `CallMethodNode`: attempt, subscribe, retry."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from machine_data_model.behavior import local_execution_node
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
from machine_data_model.tracing import (
    TraceEventType,
    TraceLevel,
    clear_traces,
    get_global_collector,
    set_global_trace_level,
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
        timeout: float | None = None,
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
            timeout=timeout,
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
            key
            for key in context._locals
            if key.startswith(("call_method_wait", "call_method_deadline"))
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


class FakeClock:
    """A clock that only moves when the test says so."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(local_execution_node, "time", fake)
    return fake


def deadline_keys(setup: Setup, context_id: str) -> list[str]:
    return [k for k in setup.wait_keys(context_id) if "deadline" in k]


@kinds
class TestTimeout:
    def test_the_first_wait_stores_the_deadline(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)

        context_id = setup.start()

        context = setup.parent._contexts[context_id]
        (key,) = deadline_keys(setup, context_id)
        assert context.get_value(key) == 1030.0

    def test_without_a_timeout_there_is_no_deadline(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee)

        context_id = setup.start()
        clock.now += 10**9
        setup.mode.write(2)
        setup.resume(context_id)

        assert deadline_keys(setup, context_id) == []
        assert setup.parent._contexts[context_id].is_active()
        assert setup.callee_runs() == 0

    def test_before_the_deadline_it_keeps_waiting_and_does_not_extend_it(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()
        (key,) = deadline_keys(setup, context_id)

        clock.now += 29
        setup.mode.write(2)
        setup.resume(context_id)

        context = setup.parent._contexts[context_id]
        assert context.is_active()
        assert context.get_value(key) == 1030.0
        assert setup.subscribers(setup.mode) == [context_id]

    def test_after_the_deadline_it_fails_with_timeout(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()

        clock.now += 31
        result = setup.resume(context_id)

        assert result.error is not None
        error = result.error
        assert error.code is ExecutionErrorCode.TIMEOUT
        assert error.node == setup.callee.qualified_name
        assert setup.callee.qualified_name in error.message
        assert "timed out after 30 s" in error.message
        # The last unmet conditions are named, the observed value is not.
        assert "mode == 2 not met" in error.message
        assert "level >= 1 not met" in error.message
        assert error.observed is None
        assert setup.callee_runs() == 0
        assert setup.after.runs == 0

    def test_timeout_removes_every_subscription_and_key(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()

        clock.now += 31
        setup.resume(context_id)

        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []
        assert setup.wait_keys(context_id) == []

    def test_exactly_at_the_deadline_is_a_timeout(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()

        clock.now += 30
        result = setup.resume(context_id)

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.TIMEOUT

    def test_one_last_attempt_wins_over_the_deadline(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()
        # The requires came true without any event; nobody resumed in time.
        setup.mode._update_internal_value(2)
        setup.level._update_internal_value(1)

        clock.now += 500
        result = setup.resume(context_id)

        assert result.error is None
        assert setup.callee_runs() == 1
        assert setup.after.runs == 1
        assert setup.wait_keys(context_id) == []

    def test_a_met_requires_clears_the_deadline(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()
        assert deadline_keys(setup, context_id)

        setup.mode.write(2)
        setup.level.write(1)
        setup.resume(context_id)

        assert setup.wait_keys(context_id) == []

    def test_contexts_have_their_own_deadlines(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        first = setup.start()
        clock.now += 20
        second = setup.start()

        clock.now += 15
        late = setup.resume(first)
        early = setup.resume(second)

        assert late.error is not None
        assert late.error.code is ExecutionErrorCode.TIMEOUT
        assert early.error is None
        assert setup.parent._contexts[second].is_active()

    def test_configuration_error_after_waiting_is_not_a_timeout(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()
        setup.callee._requires = (Condition("nope", EQ, 1),)

        clock.now += 31
        result = setup.resume(context_id)

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert setup.wait_keys(context_id) == []

    def test_the_message_is_bounded_with_many_unmet_conditions(
        self, composite_callee: bool, clock: FakeClock
    ) -> None:
        many = [Condition("mode", EQ, 100 + i) for i in range(300)]
        setup = Setup(composite_callee, requires=many, timeout=30)
        context_id = setup.start()

        clock.now += 31
        result = setup.resume(context_id)

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.TIMEOUT
        assert len(result.error.message) <= 768
        assert "\n" not in result.error.message


def test_fractional_timeout_is_written_compactly(clock: FakeClock) -> None:
    setup = Setup(timeout=2.5)
    context_id = setup.start()

    clock.now += 3
    result = setup.resume(context_id)

    assert result.error is not None
    assert "timed out after 2.5 s" in result.error.message


@kinds
class TestRelease:
    """A wait is released wherever the context ends."""

    def test_abort_mid_wait_removes_everything(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()
        assert setup.subscribers(setup.mode) == [context_id]
        assert deadline_keys(setup, context_id)

        messages = setup.parent.abort_context(context_id)

        assert messages == []
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []
        assert setup.parent._contexts == {}
        assert setup.data_model._contexts == {}

    def test_abort_leaves_the_other_context_waiting(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        first = setup.start()
        second = setup.start()

        setup.parent.abort_context(first)

        assert setup.subscribers(setup.mode) == [second]
        setup.mode.write(2)
        setup.resume(second)
        assert setup.callee_runs() == 1

    def test_release_can_be_repeated(self, composite_callee: bool) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()
        context = setup.parent._contexts[context_id]

        assert setup.call.release(context) == []
        assert setup.call.release(context) == []

        assert setup.subscribers(setup.mode) == []
        assert setup.wait_keys(context_id) == []

    def test_release_without_a_wait_is_a_no_op(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, mode=2, level=1)
        result = setup.parent()
        assert result.error is None

        from machine_data_model.behavior.execution_context import (
            ExecutionContext,
        )

        fresh = ExecutionContext("fresh")
        assert setup.call.release(fresh) == []

    def test_an_unexpected_error_after_waiting_releases_the_wait(
        self, composite_callee: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ControlFlow, "default_strict", False)
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        context_id = setup.start()
        assert setup.subscribers(setup.mode) == [context_id]

        def boom(**kwargs: Any) -> None:
            raise RuntimeError("callee exploded")

        if composite_callee:
            setup.callee_stub._make = boom  # type: ignore[assignment]
        else:
            setup.callee._callback = boom
        setup.mode.write(2)
        result = setup.resume(context_id)

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert setup.subscribers(setup.mode) == []
        assert setup.wait_keys(context_id) == []


class TestNestedRelease:
    def test_aborting_the_grandparent_releases_the_inner_wait(self) -> None:
        setup = Setup()
        outer = CallMethodNode(
            method_node="parent", args=[], kwargs={}, on_unmet="fail"
        )
        outer.set_ref_node(setup.parent)
        grandparent = CompositeMethodNode(
            id="gp", name="gp", cfg=ControlFlow(nodes=[outer])
        )
        setup.data_model.root.add_child(grandparent)
        setup.data_model._register_nodes(setup.data_model.root)

        result = grandparent()
        gp_context = result.return_values["@context_id"]
        assert len(setup.subscribers(setup.mode)) == 1
        assert len(setup.parent._contexts) == 1

        grandparent.abort_context(gp_context)

        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []
        assert setup.parent._contexts == {}
        assert grandparent._contexts == {}
        assert setup.data_model._contexts == {}


@kinds
class TestCalleeThatWritesWatchedVariables:
    """The wait is dropped while the callee runs: no re-entrant resume."""

    @staticmethod
    def build(composite_callee: bool, writes: str) -> Setup:
        setup = Setup(
            composite_callee,
            requires=[
                Condition("mode", GE, 1),
                Condition("level", GE, 0),
            ],
            mode=0,
            level=0,
        )
        target = setup.mode if writes == "mode" else setup.level
        value = 5

        def write() -> None:
            target.write(value)

        if composite_callee:

            def make() -> Any:
                write()
                return execution_success()

            setup.callee_stub._make = make
        else:
            real = setup.callee._callback

            def callback(**kwargs: Any) -> int:
                write()
                return real(**kwargs)  # type: ignore[no-any-return]

            setup.callee._callback = callback
        return setup

    @staticmethod
    def resume_synchronously(setup: Setup) -> list[str]:
        resumed: list[str] = []

        def on_change(subscription: Any, node: Any, value: Any) -> None:
            resumed.append(subscription.subscriber_id)
            setup.parent.resume_execution(subscription.subscriber_id)

        for variable in (setup.mode, setup.level):
            variable.set_subscription_callback(on_change)
        return resumed

    @pytest.mark.parametrize("writes", ["mode", "level"])
    def test_the_callee_is_called_exactly_once(
        self, composite_callee: bool, writes: str
    ) -> None:
        setup = self.build(composite_callee, writes)
        resumed = self.resume_synchronously(setup)
        context_id = setup.start()
        assert setup.subscribers(setup.mode) == [context_id]

        setup.mode.write(1)

        assert setup.callee_runs() == 1
        assert setup.after.runs == 1
        # Only the write that made the requires true woke the context.
        assert resumed == [context_id]
        assert setup.subscribers(setup.mode) == []
        assert setup.subscribers(setup.level) == []
        assert setup.wait_keys(context_id) == []

    def test_the_wait_is_not_installed_during_the_call(
        self, composite_callee: bool
    ) -> None:
        setup = self.build(composite_callee, "level")
        context_id = setup.start()
        seen: list[list[str]] = []
        real_write = setup.level.write

        def spy(value: Any) -> bool:
            seen.append(setup.subscribers(setup.mode))
            return real_write(value)

        setup.level.write = spy  # type: ignore[method-assign]
        setup.mode.write(1)
        setup.resume(context_id)

        assert seen
        assert all(subscribers == [] for subscribers in seen)

    def test_a_rejection_after_the_resume_subscribes_again(
        self, composite_callee: bool
    ) -> None:
        setup = self.build(composite_callee, "level")
        context_id = setup.start()

        # Woken, but still unmet: the node must be waiting again.
        setup.level.write(3)
        setup.resume(context_id)

        assert setup.callee_runs() == 0
        assert setup.subscribers(setup.mode) == [context_id]
        assert setup.subscribers(setup.level) == [context_id]

    def test_the_deadline_survives_the_resubscription(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(
            composite_callee,
            requires=[Condition("mode", GE, 1)],
            mode=0,
            timeout=30,
        )
        context_id = setup.start()
        (key,) = deadline_keys(setup, context_id)
        context = setup.parent._contexts[context_id]
        deadline = context.get_value(key)

        setup.level.write(3)
        setup.resume(context_id)

        assert context.get_value(key) == deadline


class Scripted(NumericalVariableNode):
    """A variable whose successive reads follow a script (2 holds, 1 not)."""

    def __init__(self, script: list[float], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.script = list(script)
        self.reads = 0

    def read(self, force_remote_read: bool = True) -> Any:
        self.reads += 1
        if self.script:
            return self.script.pop(0)
        return 2


def scripted_setup(script: list[float]) -> tuple[Setup, Scripted]:
    setup = Setup(requires=[Condition("mode", EQ, 2)])
    flapping = Scripted(script, id="mode", name="mode", value=1)
    flapping.set_subscription_callback(setup.on_change)
    setup.data_model.root.remove_child("mode")
    setup.data_model.root.add_child(flapping)
    setup.data_model._register_nodes(setup.data_model.root)
    setup.mode = flapping
    return setup, flapping


# reject, pass, reject, pass ... as many looks as the cap needs.
FLIPPING: list[float] = [1.0, 2.0] * 4 + [1.0]


class TestLastCycleIsAuthoritative:
    def test_a_value_that_flips_once_is_caught_by_the_recheck(self) -> None:
        # Rejected, then holds when looked at again: one more real call.
        setup, flapping = scripted_setup([1.0, 2.0, 2.0])

        result = setup.parent()

        assert result.error is None
        assert setup.callee_runs() == 1
        assert setup.after.runs == 1
        assert flapping.reads == 3
        assert setup.subscribers(flapping) == []

    def test_a_value_that_keeps_flipping_ends_with_a_real_call(self) -> None:
        # reject, pass, reject, pass, ... : every look after a rejection says
        # "it holds now", so the node keeps going round.
        setup, flapping = scripted_setup(FLIPPING)

        result = setup.parent()

        # Five real calls and four checks: the last cycle does not check again
        # (there would be no call left to act on a check that passed).
        assert flapping.reads == 9
        assert setup.callee_runs() == 0
        context_id = result.return_values["@context_id"]
        assert setup.parent._contexts[context_id].is_active()
        # It waits, subscribed, for the next change.
        assert setup.subscribers(flapping) == [context_id]

    def test_after_the_cap_the_next_event_resumes_and_calls(self) -> None:
        setup, flapping = scripted_setup(FLIPPING)
        context_id = setup.start()
        assert setup.callee_runs() == 0

        flapping._update_internal_value(5)
        flapping.notify_subscribers()
        assert setup.woken == [context_id]
        setup.resume(context_id)

        # The script is exhausted: the variable holds from now on.
        assert setup.callee_runs() == 1
        assert setup.subscribers(flapping) == []
        assert setup.wait_keys(context_id) == []

    def test_the_cap_is_a_module_constant(self) -> None:
        assert local_execution_node._MAX_WAIT_CYCLES == 5


class Counting(NumericalVariableNode):
    """A parameter node that counts how often it is read."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.reads = 0

    def read(self, force_remote_read: bool = True) -> Any:
        self.reads += 1
        return super().read(force_remote_read)


class TestArgumentsAreResolvedOnce:
    @staticmethod
    def build(script: list[float] | None = None) -> tuple[Setup, Counting]:
        parameter = Counting(id="p", name="p", value=7)
        setup = Setup(
            requires=[Condition("mode", EQ, 2)],
            callee_parameters=[parameter],
        )
        if script is not None:
            flapping = Scripted(script, id="mode", name="mode", value=1)
            flapping.set_subscription_callback(setup.on_change)
            setup.data_model.root.remove_child("mode")
            setup.data_model.root.add_child(flapping)
            setup.data_model._register_nodes(setup.data_model.root)
            setup.mode = flapping
        return setup, parameter

    def test_a_call_that_holds_reads_the_parameter_once(self) -> None:
        setup, parameter = self.build()
        setup.mode._update_internal_value(2)

        setup.parent()

        assert parameter.reads == 1
        assert setup.calls == [{"p": 7}]

    def test_all_the_cycles_of_one_step_share_one_read(self) -> None:
        # Nine looks at the condition (five calls, four checks), one read.
        setup, parameter = self.build(FLIPPING)

        setup.parent()

        assert setup.mode.reads == 9  # type: ignore[attr-defined]
        assert parameter.reads == 1

    def test_each_resume_reads_it_once_more(self) -> None:
        setup, parameter = self.build()
        context_id = setup.start()
        assert parameter.reads == 1

        setup.mode.write(3)
        setup.resume(context_id)

        # Still unmet: one more step, one more read (not two).
        assert parameter.reads == 2

    def test_the_callee_gets_the_value_that_was_read(self) -> None:
        setup, parameter = self.build()
        context_id = setup.start()
        parameter._update_internal_value(9)
        setup.mode.write(2)

        setup.resume(context_id)

        assert setup.calls == [{"p": 9}]

    def test_a_given_argument_is_not_read_at_all(self) -> None:
        parameter = Counting(id="p", name="p", value=7)
        setup = Setup(
            requires=[Condition("mode", EQ, 2)],
            callee_parameters=[parameter],
            call_kwargs={"p": 42},
            mode=2,
        )

        setup.parent()

        assert parameter.reads == 0
        assert setup.calls == [{"p": 42}]

    def test_fail_mode_also_reads_once(self) -> None:
        parameter = Counting(id="p", name="p", value=7)
        setup = Setup(
            requires=[Condition("mode", EQ, 2)],
            callee_parameters=[parameter],
            on_unmet="fail",
        )

        setup.parent()

        assert parameter.reads == 1


@pytest.fixture
def traces() -> Any:
    clear_traces()
    set_global_trace_level(TraceLevel.FULL)
    yield get_global_collector()
    set_global_trace_level(TraceLevel.NONE)
    clear_traces()


def starts(collector: Any) -> list[Any]:
    return list(collector.get_events(TraceEventType.WAIT_START))


def ends(collector: Any) -> list[Any]:
    return list(collector.get_events(TraceEventType.WAIT_END))


@kinds
class TestWaitTrace:
    def test_one_start_at_the_first_wait(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee)

        context_id = setup.start()

        (event,) = starts(traces)
        assert event.details["variable_id"] == "callee"
        assert "mode == 2 not met" in event.details["condition"]
        assert setup.callee.qualified_name in event.source
        assert context_id in event.source
        assert event.data_model_id == "dm"
        assert ends(traces) == []

    def test_resumes_that_still_wait_do_not_start_again(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()

        setup.mode.write(3)
        setup.resume(context_id)
        setup.level.write(1)
        setup.resume(context_id)

        assert len(starts(traces)) == 1
        assert ends(traces) == []

    def test_end_when_the_call_goes_through(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()

        setup.mode.write(2)
        setup.level.write(1)
        setup.resume(context_id)

        (end,) = ends(traces)
        assert end.details["variable_id"] == "callee"
        assert end.details["wait_duration"] >= 0
        assert setup.wait_keys(context_id) == []

    def test_end_on_timeout(
        self, composite_callee: bool, traces: Any, clock: FakeClock
    ) -> None:
        setup = Setup(composite_callee, timeout=30)
        context_id = setup.start()

        clock.now += 31
        setup.resume(context_id)

        assert len(starts(traces)) == 1
        assert len(ends(traces)) == 1

    def test_end_on_a_configuration_error_after_waiting(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()
        setup.callee._requires = (Condition("nope", EQ, 1),)

        setup.resume(context_id)

        assert len(starts(traces)) == 1
        assert len(ends(traces)) == 1

    def test_end_on_release(self, composite_callee: bool, traces: Any) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()

        setup.parent.abort_context(context_id)

        assert len(starts(traces)) == 1
        assert len(ends(traces)) == 1

    def test_the_end_is_traced_once(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee)
        context_id = setup.start()
        context = setup.parent._contexts[context_id]

        setup.call.release(context)
        setup.call.release(context)

        assert len(ends(traces)) == 1

    def test_requires_that_hold_trace_no_wait(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee, mode=2, level=1)

        setup.parent()

        assert starts(traces) == []
        assert ends(traces) == []

    def test_fail_mode_traces_no_wait(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee, on_unmet="fail")

        setup.parent()

        assert starts(traces) == []
        assert ends(traces) == []

    def test_each_context_has_its_own_start_and_end(
        self, composite_callee: bool, traces: Any
    ) -> None:
        setup = Setup(composite_callee, requires=[Condition("mode", EQ, 2)])
        first = setup.start()
        second = setup.start()

        setup.parent.abort_context(first)

        assert len(starts(traces)) == 2
        assert len(ends(traces)) == 1
        assert first in ends(traces)[0].source
        setup.parent.abort_context(second)
        assert len(ends(traces)) == 2


class TestWaitTraceDetails:
    def test_nothing_is_traced_at_the_default_level(self) -> None:
        clear_traces()
        setup = Setup()
        context_id = setup.start()
        setup.mode.write(2)
        setup.level.write(1)
        setup.resume(context_id)

        collector = get_global_collector()
        assert collector.get_events(TraceEventType.WAIT_START) == []
        assert collector.get_events(TraceEventType.WAIT_END) == []
        assert setup.callee_runs() == 1

    def test_the_condition_text_is_bounded(self, traces: Any) -> None:
        many = [Condition("mode", EQ, 100 + i) for i in range(300)]
        setup = Setup(requires=many)

        setup.start()

        (event,) = starts(traces)
        assert len(event.details["condition"]) <= 256
        assert "\n" not in event.details["condition"]

    def test_the_trace_key_is_gone_after_the_end(self, traces: Any) -> None:
        setup = Setup()
        context_id = setup.start()
        context = setup.parent._contexts[context_id]
        assert any("trace" in key for key in context._locals)

        setup.parent.abort_context(context_id)

        assert not any("trace" in key for key in context._locals)
