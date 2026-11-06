"""Frost handling of nested composite contexts (a composite calling one)."""

import logging

import pytest

from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import MsgType
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorCode,
    ErrorMessages,
    ErrorPayload,
    MethodPayload,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)
from tests.behavior import (
    ERROR,
    assert_no_contexts,
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


def remote_call(method: str = "remote_method") -> CallRemoteMethodNode:
    return CallRemoteMethodNode(
        method_node=method, remote_id="remote_dm", args=[], kwargs={}
    )


def remote_response(
    request: FrostMessage,
    sender: str = "remote_dm",
    node: str = "remote_method",
    correlation_id: str | None = None,
) -> FrostMessage:
    return FrostMessageBuilder(sender=sender).build_method_completed_message(
        target=request.sender,
        correlation_id=correlation_id or str(request.correlation_id),
        ret={},
        node=node,
    )


def start_with_remote(
    *composites: CompositeMethodNode, root: str
) -> tuple[FrostProtocolMng, DataModel, FrostMessage, FrostMessage]:
    manager, data_model = frost_setup(*composites)
    response = manager.handle_request(frost_request("dm", root))
    assert isinstance(response, FrostMessage)
    sent = manager.drain_update_messages()
    requests = [m for m in sent if m.header.type is MsgType.REQUEST]
    assert len(requests) == 1
    return manager, data_model, response, requests[0]


class TestNestedRemoteCall:
    def test_response_is_routed_to_the_nested_child(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, response, request = start_with_remote(
            child, parent, root="parent"
        )
        child_id = next(iter(child._contexts))
        # The request carries the id of the context that issued it.
        assert request.correlation_id == child_id
        assert child_id in data_model._contexts
        assert child_id not in manager._running_methods

        final = manager.handle_message(remote_response(request))

        assert isinstance(final, FrostMessage)
        assert final.header.type is MsgType.RESPONSE
        assert isinstance(final.payload, MethodPayload)
        assert final.correlation_id == response.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(parent, child)
        assert manager.drain_update_messages() == []

    def test_chain_with_the_remote_call_in_the_innermost(self) -> None:
        c = composite("c", [remote_call()])
        b = composite("b", [call("c")])
        a = composite("a", [call("b")])
        manager, data_model, response, request = start_with_remote(
            c, b, a, root="a"
        )
        assert len(data_model._contexts) == 3

        final = manager.handle_message(remote_response(request))

        assert isinstance(final, FrostMessage)
        assert final.correlation_id == response.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(a, b, c)

    def test_top_level_remote_call_is_unchanged(self) -> None:
        method = composite("m", [remote_call()])
        manager, data_model, response, request = start_with_remote(
            method, root="m"
        )

        final = manager.handle_message(remote_response(request))

        assert isinstance(final, FrostMessage)
        assert final.correlation_id == response.correlation_id
        assert data_model._contexts == {}

    def test_response_from_the_wrong_sender_is_ignored(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, _, request = start_with_remote(
            child, parent, root="parent"
        )

        assert (
            manager.handle_message(remote_response(request, sender="intruder"))
            is None
        )

        assert len(manager._running_methods) == 1
        assert len(data_model._contexts) == 2

    def test_response_for_the_wrong_node_is_ignored(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, _, request = start_with_remote(
            child, parent, root="parent"
        )

        assert (
            manager.handle_message(
                remote_response(request, node="other_method")
            )
            is None
        )

        assert len(data_model._contexts) == 2

    def test_response_with_an_unknown_correlation_id_is_ignored(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, _, request = start_with_remote(
            child, parent, root="parent"
        )

        assert (
            manager.handle_message(
                remote_response(request, correlation_id="unknown")
            )
            is None
        )

        assert len(manager._running_methods) == 1
        assert len(data_model._contexts) == 2

    def test_duplicate_response_is_a_no_op(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, _, request = start_with_remote(
            child, parent, root="parent"
        )
        assert manager.handle_message(remote_response(request)) is not None

        assert manager.handle_message(remote_response(request)) is None

        assert manager._running_methods == {}
        assert data_model._contexts == {}


class TestFinishEdgeCases:
    def test_released_root_is_answered_with_a_generic_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        manager, data_model, response = started(
            child, trigger=trigger, root="child"
        )
        (root_id,) = manager._running_methods
        # Somebody released the context behind the manager's back.
        child.delete_context(root_id)

        with caplog.at_level(logging.WARNING):
            answer = manager._finish_if_terminated(root_id)

        assert isinstance(answer, FrostMessage)
        assert answer.header.type is MsgType.ERROR
        assert answer.correlation_id == response.correlation_id
        assert isinstance(answer.payload, ErrorPayload)
        assert answer.payload.error_code is ErrorCode.UNKNOWN
        assert (
            answer.payload.error_message == ErrorMessages.UNEXPECTED_ERROR.value
        )
        assert manager._running_methods == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert str(response.correlation_id) in warnings[0].getMessage()
        # Idempotent: the request is gone, a second call answers nothing.
        assert manager._finish_if_terminated(root_id) is None

    def test_root_walk_logs_when_it_ends_off_a_running_request(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        manager, data_model, _ = started(child, trigger=trigger, root="child")
        (root_id,) = manager._running_methods

        with caplog.at_level(logging.DEBUG):
            assert manager._root_context_id(root_id) == root_id
            quiet = [r for r in caplog.records if "walk up" in r.getMessage()]
            assert manager._root_context_id("unknown") == "unknown"
            noisy = [r for r in caplog.records if "walk up" in r.getMessage()]

        assert quiet == []
        assert len(noisy) == 1
        assert "unknown" in noisy[0].getMessage()
