"""Tests for the DataModel index of live execution contexts."""

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    execution_error,
)
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
)
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    LocalExecutionNode,
    WaitConditionNode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode


def composite(name: str, nodes: list[ControlFlowNode]) -> CompositeMethodNode:
    return CompositeMethodNode(
        id=name, name=name, cfg=ControlFlow(nodes=list(nodes))
    )


def wait_for_nonzero(trigger: NumericalVariableNode) -> WaitConditionNode:
    node = WaitConditionNode(
        variable_node=trigger.id, rhs=0, op=WaitConditionOperator.NE
    )
    return node


def call(name: str) -> CallMethodNode:
    return CallMethodNode(method_node=name, args=[], kwargs={})


def build_model(
    *nodes: CompositeMethodNode | NumericalVariableNode,
) -> DataModel:
    """Register callees before callers (static references are resolved in
    registration order)."""
    data_model = DataModel(name="dm")
    for node in nodes:
        data_model.root.add_child(node)
    data_model._register_nodes(data_model.root)
    return data_model


def chain() -> (
    tuple[
        DataModel,
        NumericalVariableNode,
        CompositeMethodNode,
        CompositeMethodNode,
        CompositeMethodNode,
    ]
):
    """Build a -> b -> c, where c waits on a trigger."""
    trigger = NumericalVariableNode(id="t", name="t", value=0)
    c = composite("c", [wait_for_nonzero(trigger)])
    b = composite("b", [call("c")])
    a = composite("a", [call("b")])
    return build_model(trigger, c, b, a), trigger, a, b, c


class TestIndex:
    def test_unknown_id_is_none(self) -> None:
        data_model = build_model()

        assert data_model.find_context("nope") is None

    def test_pending_context_is_indexed_with_its_owner(self) -> None:
        data_model, trigger, a, _, _ = chain()

        ctx_id = a().return_values["@context_id"]

        found = data_model.find_context(ctx_id)
        assert found is not None
        owner, context = found
        assert owner is a
        assert context is a._get_context(ctx_id)

    def test_nested_children_are_indexed_at_every_level(self) -> None:
        data_model, trigger, a, b, c = chain()

        a_id = a().return_values["@context_id"]

        assert len(data_model._contexts) == 3
        owners = {
            owner.name: ctx_id
            for ctx_id, (owner, _) in data_model._contexts.items()
        }
        assert set(owners) == {"a", "b", "c"}
        assert owners["a"] == a_id
        for name, composite_node in (("a", a), ("b", b), ("c", c)):
            found = data_model.find_context(owners[name])
            assert found is not None
            assert found[0] is composite_node

    def test_delete_context_unindexes(self) -> None:
        data_model, trigger, a, _, _ = chain()
        a_id = a().return_values["@context_id"]

        a.delete_context(a_id)

        assert data_model.find_context(a_id) is None

    def test_full_completion_and_collection_leaves_nothing(self) -> None:
        data_model, trigger, a, b, c = chain()
        a_id = a().return_values["@context_id"]
        c_id = next(iter(c._contexts))
        trigger.write(1)

        c.resume_execution(c_id)

        # The cascade deleted the child contexts; the root waits to be
        # collected by its consumer.
        assert list(data_model._contexts) == [a_id]
        a.delete_context(a_id)
        assert data_model._contexts == {}

    def test_sync_completion_is_released_and_unindexed(self) -> None:
        method = composite("m", [])
        data_model = build_model(method)

        method()

        assert data_model._contexts == {}
        assert method._contexts == {}

    def test_sync_failure_is_released_and_unindexed(self) -> None:
        class Failing(LocalExecutionNode):
            def __init__(self) -> None:
                super().__init__(node="")

            def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
                return execution_error(
                    ExecutionError(ExecutionErrorCode.TIMEOUT, "x")
                )

        method = composite("m", [Failing()])
        data_model = build_model(method)

        assert method().error is not None

        assert data_model._contexts == {}

    def test_abort_context_unindexes_it_and_its_children(self) -> None:
        data_model, trigger, a, b, c = chain()
        a_id = a().return_values["@context_id"]
        assert len(data_model._contexts) == 3

        # Aborting the root releases the node it waits on (the call node),
        # which aborts the child chain.
        a.abort_context(a_id)

        assert data_model._contexts == {}
        assert trigger.get_subscriptions() == []
        assert a._contexts == b._contexts == c._contexts == {}

    def test_abort_unknown_context_is_ignored(self) -> None:
        data_model = build_model()
        method = composite("m", [])
        data_model.root.add_child(method)
        data_model._register_nodes(data_model.root)

        method.abort_context("nope")

        assert data_model._contexts == {}

    def test_two_invocations_are_indexed_separately(self) -> None:
        data_model, trigger, a, _, _ = chain()

        first = a().return_values["@context_id"]
        second = a().return_values["@context_id"]

        assert first != second
        assert len(data_model._contexts) == 6
        a.delete_context(first)
        assert data_model.find_context(first) is None
        assert data_model.find_context(second) is not None

    def test_composite_without_a_data_model_does_not_index(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        wait = wait_for_nonzero(trigger)
        wait.set_ref_node(trigger)
        method = composite("m", [wait])

        ctx_id = method().return_values["@context_id"]
        method.resume_execution(ctx_id)
        trigger.write(1)
        method.resume_execution(ctx_id)
        method.delete_context(ctx_id)

        assert method._contexts == {}
