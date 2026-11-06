"""Frost handling of nested composite contexts (a composite calling one)."""

from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import MsgType
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorCode,
    ErrorPayload,
    MethodPayload,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)
from tests.behavior import (
    ERROR,
    composite,
    failing_stub,
    frost_request,
    frost_setup,
    wait_for_nonzero,
)


def call(name: str) -> CallMethodNode:
    return CallMethodNode(method_node=name, args=[], kwargs={})


def started(
    *composites: CompositeMethodNode,
    trigger: NumericalVariableNode,
    root: str,
) -> tuple[FrostProtocolMng, DataModel, FrostMessage]:
    manager, data_model = frost_setup(*composites, variables=(trigger,))
    response = manager.handle_request(frost_request("dm", root))
    assert isinstance(response, FrostMessage)
    manager.clear_update_messages()
    return manager, data_model, response


class TestNestedResume:
    def test_updates_are_only_the_method_response(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        parent = composite("parent", [call("child")])
        manager, data_model, response = started(
            child, parent, trigger=trigger, root="parent"
        )

        trigger.write(1)

        updates = manager.drain_update_messages()
        # No spurious VARIABLE UPDATE addressed to the child context id.
        assert [type(u.payload) for u in updates] == [MethodPayload]
        assert updates[0].correlation_id == response.correlation_id

    def test_nested_wait_ending_in_failure_answers_with_an_error(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger), failing_stub()])
        parent = composite("parent", [call("child")])
        manager, data_model, response = started(
            child, parent, trigger=trigger, root="parent"
        )

        trigger.write(1)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.ERROR
        assert updates[0].correlation_id == response.correlation_id
        assert isinstance(updates[0].payload, ErrorPayload)
        assert updates[0].payload.error_code is ErrorCode.NOT_ALLOWED
        assert ERROR.message in updates[0].payload.error_message
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert trigger.get_subscriptions() == []

    def test_grandparent_chain_is_answered_exactly_once(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        c = composite("c", [wait_for_nonzero(trigger)])
        b = composite("b", [call("c")])
        a = composite("a", [call("b")])
        manager, data_model, response = started(
            c, b, a, trigger=trigger, root="a"
        )
        assert len(data_model._contexts) == 3

        trigger.write(1)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert isinstance(updates[0].payload, MethodPayload)
        assert updates[0].correlation_id == response.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        for method in (a, b, c):
            assert method._contexts == {}
            assert method._completed_results == {}

    def test_root_id_is_found_before_the_cascade_breaks_the_links(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        c = composite("c", [wait_for_nonzero(trigger)])
        b = composite("b", [call("c")])
        a = composite("a", [call("b")])
        manager, data_model, response = started(
            c, b, a, trigger=trigger, root="a"
        )
        (root_id,) = manager._running_methods
        c_id = next(iter(c._contexts))
        b_id = next(iter(b._contexts))

        assert manager._root_context_id(c_id) == root_id
        assert manager._root_context_id(b_id) == root_id
        assert manager._root_context_id(root_id) == root_id
        assert manager._root_context_id("unknown") == "unknown"

    def test_duplicate_trigger_is_a_no_op(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        parent = composite("parent", [call("child")])
        manager, data_model, _ = started(
            child, parent, trigger=trigger, root="parent"
        )

        trigger.write(1)
        trigger.write(2)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert data_model._contexts == {}

    def test_two_requests_are_answered_independently(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        parent = composite("parent", [call("child")])
        manager, data_model, first = started(
            child, parent, trigger=trigger, root="parent"
        )
        second = manager.handle_request(frost_request("dm", "parent"))
        assert isinstance(second, FrostMessage)
        manager.clear_update_messages()
        assert len(manager._running_methods) == 2

        trigger.write(1)

        updates = manager.drain_update_messages()
        assert sorted(str(u.correlation_id) for u in updates) == sorted(
            [str(first.correlation_id), str(second.correlation_id)]
        )
        assert manager._running_methods == {}
        assert data_model._contexts == {}

    def test_unknown_context_is_ignored(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        manager, data_model, _ = started(child, trigger=trigger, root="child")

        assert manager._resume_composite_method("nope") is None

        assert len(manager._running_methods) == 1
        assert manager.drain_update_messages() == []

    def test_finish_is_idempotent(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        manager, data_model, _ = started(child, trigger=trigger, root="child")
        (root_id,) = manager._running_methods
        assert manager._finish_if_terminated(root_id) is None

        trigger.write(1)

        manager.drain_update_messages()
        assert manager._finish_if_terminated(root_id) is None
        assert manager._running_methods == {}

    def test_top_level_wait_still_works(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        manager, data_model, response = started(
            child, trigger=trigger, root="child"
        )

        trigger.write(1)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].correlation_id == response.correlation_id
        assert isinstance(updates[0].payload, MethodPayload)
