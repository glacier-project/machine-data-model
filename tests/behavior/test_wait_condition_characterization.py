"""Characterization tests for the current behavior of `WaitConditionNode`.

These tests pin down the behavior of `WaitConditionNode` (and of the composite
callee path of `CallMethodNode`) *as it is today*. They are a safety net for
refactors of the condition evaluation logic: when a test here fails, behavior
changed and the change must be deliberate.
"""

from collections.abc import Callable
import operator as py_operator
from typing import Any
import uuid

import pytest

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
    WaitConditionNode,
    WaitConditionOperator,
    get_condition_operator,
)
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
    ContextNotFoundError,
)
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
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

OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "==": py_operator.eq,
    "!=": py_operator.ne,
    "<": py_operator.lt,
    ">": py_operator.gt,
    "<=": py_operator.le,
    ">=": py_operator.ge,
}

# (variable factory, lhs value, rhs values to compare against).
# Bool is ordered False < True by Python, so all six operators are defined.
TYPED_CASES: dict[str, tuple[Callable[[], VariableNode], list[Any]]] = {
    "numeric": (
        lambda: NumericalVariableNode(name="v", value=5),
        [4, 5, 6],
    ),
    "string": (
        lambda: StringVariableNode(name="v", value="bbb"),
        ["aaa", "bbb", "ccc"],
    ),
    "bool": (
        lambda: BooleanVariableNode(name="v", value=True),
        [False, True],
    ),
}


def new_context(**values: Any) -> ExecutionContext:
    context = ExecutionContext(str(uuid.uuid4()))
    for key, value in values.items():
        context.set_value(key, value)
    return context


def make_wait(variable: VariableNode, op: str, rhs: Any) -> WaitConditionNode:
    node = WaitConditionNode(
        variable_node=variable.name,
        rhs=rhs,
        op=get_condition_operator(op),
    )
    node.set_ref_node(variable)
    return node


def wait_keys(context: ExecutionContext) -> list[str]:
    return [key for key in context.locals() if key.startswith("wait_")]


@pytest.fixture(autouse=True)
def reset_tracing() -> Any:
    clear_traces()
    yield
    set_global_trace_level(TraceLevel.NONE)
    clear_traces()


class TestOperatorsAndTypes:
    """All six operators against numeric, string and bool variables."""

    @pytest.mark.parametrize("op", list(OPERATORS))
    @pytest.mark.parametrize("type_name", list(TYPED_CASES))
    def test_constant_rhs(self, type_name: str, op: str) -> None:
        factory, rhs_values = TYPED_CASES[type_name]
        for rhs in rhs_values:
            variable = factory()
            expected = OPERATORS[op](variable.read(), rhs)

            result = make_wait(variable, op, rhs).execute(new_context())

            assert result.success is expected, (type_name, op, rhs)
            assert result.messages == []

    @pytest.mark.parametrize("op", list(OPERATORS))
    @pytest.mark.parametrize("type_name", list(TYPED_CASES))
    def test_template_rhs(self, type_name: str, op: str) -> None:
        factory, rhs_values = TYPED_CASES[type_name]
        for rhs in rhs_values:
            variable = factory()
            expected = OPERATORS[op](variable.read(), rhs)
            context = new_context(threshold=rhs)

            result = make_wait(variable, op, "${threshold}").execute(context)

            assert result.success is expected, (type_name, op, rhs)

    def test_template_rhs_embedded_in_string_is_stringified(self) -> None:
        variable = StringVariableNode(name="v", value="id-7")
        context = new_context(n=7)

        result = make_wait(variable, "==", "id-${n}").execute(context)

        assert result.success

    def test_template_rhs_missing_in_context_raises_key_error(self) -> None:
        variable = NumericalVariableNode(name="v", value=1)

        with pytest.raises(KeyError):
            make_wait(variable, "==", "${missing}").execute(new_context())

    def test_template_rhs_is_resolved_at_each_execution(self) -> None:
        variable = NumericalVariableNode(name="v", value=5)
        context = new_context(threshold=10)
        wait = make_wait(variable, ">=", "${threshold}")

        assert not wait.execute(context).success
        context.set_value("threshold", 3)
        assert wait.execute(context).success

    def test_mixed_type_comparison_raises_type_error(self) -> None:
        """Ordering operators on incompatible types propagate TypeError."""
        variable = StringVariableNode(name="v", value="abc")

        with pytest.raises(TypeError):
            make_wait(variable, "<", 3).execute(new_context())

    def test_mixed_type_equality_is_false_not_error(self) -> None:
        variable = StringVariableNode(name="v", value="3")

        assert not make_wait(variable, "==", 3).execute(new_context()).success
        assert make_wait(variable, "!=", 3).execute(new_context()).success

    def test_invalid_operator_string(self) -> None:
        with pytest.raises(ValueError):
            get_condition_operator("=<")

    def test_operator_enum_values(self) -> None:
        assert {op.value for op in WaitConditionOperator} == set(OPERATORS)


class TestWaitSubscriptionLifecycle:
    def test_condition_met_immediately_does_not_subscribe(self) -> None:
        variable = NumericalVariableNode(name="v", value=5)
        context = new_context()

        result = make_wait(variable, "==", 5).execute(context)

        assert result.success
        assert variable.get_subscriptions() == []
        assert wait_keys(context) == []

    def test_not_met_subscribes_and_stores_context_keys(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        context = new_context()

        result = make_wait(variable, ">=", 5).execute(context)

        assert not result.success
        subscriptions = variable.get_subscriptions()
        assert len(subscriptions) == 1
        assert subscriptions[0].subscriber_id == context.id()
        # Exactly two keys: the subscription and the wait start time.
        assert len(wait_keys(context)) == 2
        assert any(k.endswith("_subscription") for k in wait_keys(context))
        assert any(k.endswith("_start") for k in wait_keys(context))

    def test_repeated_execution_while_not_met_subscribes_once(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        context = new_context()
        wait = make_wait(variable, ">=", 5)

        for _ in range(3):
            assert not wait.execute(context).success

        assert len(variable.get_subscriptions()) == 1
        assert len(wait_keys(context)) == 2

    def test_write_notifies_then_resume_unsubscribes_and_cleans_context(
        self,
    ) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        context = new_context()
        notified: list[tuple[str, Any]] = []
        context.set_subscription_callback(
            lambda sub, node, value: notified.append((sub.subscriber_id, value))
        )
        wait = make_wait(variable, ">=", 5)

        assert not wait.execute(context).success

        assert variable.write(7)
        assert notified == [(context.id(), 7)]
        # Notification alone does not resume: subscription still in place.
        assert len(variable.get_subscriptions()) == 1

        # Resume = re-execute the node.
        assert wait.execute(context).success
        assert variable.get_subscriptions() == []
        assert wait_keys(context) == []

    def test_subscription_created_without_callback_gets_context_one(
        self,
    ) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        context = new_context()
        wait = make_wait(variable, ">=", 5)

        assert not wait.execute(context).success
        subscription = variable.get_subscriptions()[0]
        assert subscription.subscription_callback is None

        context.set_subscription_callback(lambda *_: None)
        assert not wait.execute(context).success

        assert subscription.subscription_callback is not None

    def test_met_after_subscribe_with_unrelated_write_stays_waiting(
        self,
    ) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        context = new_context()
        wait = make_wait(variable, ">=", 5)

        assert not wait.execute(context).success
        variable.write(2)
        assert not wait.execute(context).success

        assert len(variable.get_subscriptions()) == 1

    def test_subscriptions_are_per_context(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        wait = make_wait(variable, ">=", 5)
        context_a = new_context()
        context_b = new_context()

        assert not wait.execute(context_a).success
        assert not wait.execute(context_b).success

        subscriptions = variable.get_subscriptions()
        assert len(subscriptions) == 2
        assert {s.subscriber_id for s in subscriptions} == {
            context_a.id(),
            context_b.id(),
        }
        assert subscriptions[0] is not subscriptions[1]

        variable.write(9)

        # Completing context A must not remove context B's subscription.
        assert wait.execute(context_a).success
        remaining = variable.get_subscriptions()
        assert [s.subscriber_id for s in remaining] == [context_b.id()]
        assert wait_keys(context_a) == []
        assert len(wait_keys(context_b)) == 2

        assert wait.execute(context_b).success
        assert variable.get_subscriptions() == []

    def test_same_context_can_wait_again_after_completion(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        context = new_context()
        wait = make_wait(variable, ">=", 5)

        assert not wait.execute(context).success
        variable.write(5)
        assert wait.execute(context).success

        variable.write(0)
        assert not wait.execute(context).success

        assert len(variable.get_subscriptions()) == 1
        assert len(wait_keys(context)) == 2


class TestWaitTracing:
    def test_wait_start_and_end_are_paired(self) -> None:
        set_global_trace_level(TraceLevel.COMMUNICATION)
        variable = NumericalVariableNode(id="counter", name="v", value=0)
        context = new_context()
        wait = make_wait(variable, ">=", 5)
        collector = get_global_collector()

        assert not wait.execute(context).success
        assert len(collector.get_events(TraceEventType.WAIT_START)) == 1
        assert len(collector.get_events(TraceEventType.WAIT_END)) == 0

        # Re-executing while still waiting must not emit another start.
        assert not wait.execute(context).success
        assert len(collector.get_events(TraceEventType.WAIT_START)) == 1

        variable.write(5)
        assert wait.execute(context).success

        starts = collector.get_events(TraceEventType.WAIT_START)
        ends = collector.get_events(TraceEventType.WAIT_END)
        assert len(starts) == 1
        assert len(ends) == 1
        assert starts[0].details["variable_id"] == "counter"
        assert starts[0].details["condition"] == "0 >= 5"
        assert starts[0].details["expected_value"] == 5
        assert ends[0].details["variable_id"] == "counter"
        assert ends[0].details["wait_duration"] > 0
        assert ends[0].timestamp_ns >= starts[0].timestamp_ns

    def test_condition_met_immediately_emits_no_wait_events(self) -> None:
        set_global_trace_level(TraceLevel.COMMUNICATION)
        variable = NumericalVariableNode(name="v", value=5)
        collector = get_global_collector()

        assert make_wait(variable, "==", 5).execute(new_context()).success

        assert collector.get_events(TraceEventType.WAIT_START) == []
        assert collector.get_events(TraceEventType.WAIT_END) == []

    def test_wait_condition_text_uses_resolved_rhs(self) -> None:
        set_global_trace_level(TraceLevel.COMMUNICATION)
        variable = NumericalVariableNode(name="v", value=1)
        context = new_context(limit=9)
        collector = get_global_collector()

        make_wait(variable, "<", "${limit}").execute(context)
        make_wait(variable, ">", "${limit}").execute(context)

        starts = collector.get_events(TraceEventType.WAIT_START)
        assert len(starts) == 1
        assert starts[0].details["condition"] == "1 > 9"
        assert starts[0].details["expected_value"] == 9

    def test_two_contexts_trace_independent_pairs(self) -> None:
        set_global_trace_level(TraceLevel.COMMUNICATION)
        variable = NumericalVariableNode(name="v", value=0)
        wait = make_wait(variable, ">=", 5)
        context_a = new_context()
        context_b = new_context()
        collector = get_global_collector()

        wait.execute(context_a)
        wait.execute(context_b)
        variable.write(5)
        wait.execute(context_a)
        wait.execute(context_b)

        assert len(collector.get_events(TraceEventType.WAIT_START)) == 2
        assert len(collector.get_events(TraceEventType.WAIT_END)) == 2


class TestWaitWithNoValue:
    """Behavior when the variable value is unavailable (None).

    CURRENT behavior, documented as-is: the comparison is evaluated directly on
    `None`, so ordering operators raise TypeError and ==/!= compare against
    None. Phase 2 (Condition extraction) will turn an unavailable value into a
    `no_data` outcome instead of raising; these tests must then be updated
    deliberately.
    """

    @staticmethod
    def none_variable() -> NumericalVariableNode:
        variable = NumericalVariableNode(name="v", value=0)
        variable._update_internal_value(None)  # type: ignore[arg-type]
        assert variable.read() is None
        return variable

    @pytest.mark.parametrize("op", ["<", ">", "<=", ">="])
    def test_ordering_with_none_lhs_raises_type_error(self, op: str) -> None:
        variable = self.none_variable()
        context = new_context()

        with pytest.raises(TypeError):
            make_wait(variable, op, 5).execute(context)

        # Failure happens before any subscription or context bookkeeping.
        assert variable.get_subscriptions() == []
        assert wait_keys(context) == []

    def test_equality_with_none_lhs_compares_against_none(self) -> None:
        variable = self.none_variable()

        assert not make_wait(variable, "==", 5).execute(new_context()).success
        assert make_wait(variable, "!=", 5).execute(new_context()).success
        assert make_wait(variable, "==", None).execute(new_context()).success


def build_nested_models() -> (
    tuple[
        CompositeMethodNode,
        CompositeMethodNode,
        NumericalVariableNode,
        NumericalVariableNode,
    ]
):
    """Build parent -> CallMethodNode -> child composite that waits."""
    trigger = NumericalVariableNode(id="trigger", name="trigger", value=0)
    source = NumericalVariableNode(id="source", name="source", value=42)
    child_result = NumericalVariableNode(
        id="child_result", name="child_result", value=0
    )
    parent_result = NumericalVariableNode(
        id="parent_result", name="parent_result", value=0
    )

    child_wait = make_wait(trigger, "!=", 0)
    child_read = ReadVariableNode(
        variable_node="source", store_as="child_result"
    )
    child_read.set_ref_node(source)
    child = CompositeMethodNode(
        id="child",
        name="child",
        returns=[child_result],
        cfg=ControlFlow(nodes=[child_wait, child_read]),
    )

    call = CallMethodNode(method_node="child", args=[], kwargs={})
    call.set_ref_node(child)
    parent_read = ReadVariableNode(
        variable_node="source", store_as="parent_result"
    )
    parent_read.set_ref_node(source)
    parent = CompositeMethodNode(
        id="parent",
        name="parent",
        returns=[parent_result],
        cfg=ControlFlow(nodes=[call, parent_read]),
    )
    return parent, child, trigger, source


class TestCallMethodNodeCompositeCallee:
    """Pending/resume path of CallMethodNode when the callee is composite."""

    def test_callee_suspends_then_nested_resume_completes_parent(self) -> None:
        parent, child, trigger, _ = build_nested_models()

        ret = parent()

        # Parent is suspended: no return values, only its own context id.
        assert set(ret.return_values) == {"@context_id"}
        parent_ctx_id = ret.return_values["@context_id"]
        parent_ctx = parent._get_context(parent_ctx_id)
        assert parent_ctx.is_active()
        assert parent_ctx.get_pc() == 0

        # CallMethodNode stored the callee context id under a pc-based key.
        child_ctx_id = parent_ctx.get_value("call_method_pending_0")
        child_ctx = child._get_context(child_ctx_id)
        assert child_ctx.is_active()
        assert not child.is_terminated(child_ctx_id)
        # Callee was linked back to the parent for nested resume.
        assert child_ctx.get_value("__nested_parent_method__") is parent
        assert child_ctx.get_value("__nested_parent_context_id__") == (
            parent_ctx_id
        )
        # Callee is waiting on the trigger variable.
        assert len(trigger.get_subscriptions()) == 1

        trigger.write(1)
        # Resuming the CHILD cascades to the parent (no explicit parent resume).
        child_ret = child.resume_execution(child_ctx_id)

        assert child_ret.return_values == {"child_result": 42}
        assert trigger.get_subscriptions() == []
        assert not parent_ctx.is_active()
        assert parent.get_completed_return_values(parent_ctx_id) == {
            "parent_result": 42
        }
        # Pending bookkeeping was cleaned by CallMethodNode on completion.
        assert not parent_ctx.has_value("call_method_pending_0")
        with pytest.raises(ContextNotFoundError):
            child._get_context(child_ctx_id)

    def test_explicit_parent_resume_before_child_done_stays_suspended(
        self,
    ) -> None:
        parent, child, trigger, _ = build_nested_models()
        ret = parent()
        parent_ctx_id = ret.return_values["@context_id"]
        parent_ctx = parent._get_context(parent_ctx_id)
        child_ctx_id = parent_ctx.get_value("call_method_pending_0")

        resumed = parent.resume_execution(parent_ctx_id)

        # Child not terminated: the parent re-checks and stays suspended
        # without calling the child again.
        assert set(resumed.return_values) == {"@context_id"}
        assert parent_ctx.is_active()
        assert parent_ctx.get_value("call_method_pending_0") == child_ctx_id
        assert len(child._contexts) == 1
        assert len(trigger.get_subscriptions()) == 1

    def test_callee_not_blocking_completes_in_a_single_call(self) -> None:
        parent, child, trigger, _ = build_nested_models()
        trigger.write(1)  # wait condition already satisfied

        ret = parent()

        assert ret.return_values == {"parent_result": 42}
        assert trigger.get_subscriptions() == []
        # No pending key is left behind for a synchronously-completed callee.
        assert all(
            not c.has_value("call_method_pending_0")
            for c in parent._contexts.values()
        )
        # A composite that completes synchronously hands its result straight
        # to the caller, so its context is released before returning (phase 3
        # leak fix; before it, both contexts stayed in `_contexts` forever).
        assert parent._contexts == {}
        assert child._contexts == {}
        assert parent._completed_results == {}
        assert child._completed_results == {}

    def test_two_parent_invocations_get_independent_callee_contexts(
        self,
    ) -> None:
        parent, child, trigger, _ = build_nested_models()

        first = parent().return_values["@context_id"]
        second = parent().return_values["@context_id"]

        assert first != second
        assert len(trigger.get_subscriptions()) == 2
        child_ids = {
            parent._get_context(first).get_value("call_method_pending_0"),
            parent._get_context(second).get_value("call_method_pending_0"),
        }
        assert len(child_ids) == 2

        trigger.write(1)
        for child_id in child_ids:
            child.resume_execution(child_id)

        assert trigger.get_subscriptions() == []
        assert parent.get_completed_return_values(first) == {
            "parent_result": 42
        }
        assert parent.get_completed_return_values(second) == {
            "parent_result": 42
        }
