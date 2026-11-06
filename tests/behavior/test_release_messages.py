"""Release of a node can produce messages (remote unsubscribe)."""

from typing import Any

import pytest

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ExecutionNodeResult,
    execution_success,
)
from machine_data_model.behavior.execution_context import (
    ControlFlowStatus,
    ExecutionContext,
)
from machine_data_model.behavior.execution_error import ExecutionErrorCode
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    LocalExecutionNode,
)
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
    WaitRemoteEventNode,
)
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.protocols.frost_v1.frost_header import (
    MsgNamespace,
    MsgType,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from tests.behavior import assert_no_contexts, new_context


def remote_wait() -> WaitRemoteEventNode:
    node = WaitRemoteEventNode(
        variable_node="remote/var",
        remote_id="remote_dm",
        rhs=1,
        op=WaitConditionOperator.EQ,
    )
    node.set_message_builder(FrostMessageBuilder(sender="dm"))
    return node


def assert_unsubscribe(
    message: FrostMessage, context: ExecutionContext
) -> None:
    assert message.header.type is MsgType.REQUEST
    assert message.header.namespace is MsgNamespace.VARIABLE
    assert message.header.msg_name is VariableMsgName.UNSUBSCRIBE
    assert message.target == "remote_dm"
    assert message.sender == "dm"
    assert message.correlation_id == context.id()


class Messaging(LocalExecutionNode):
    """Node whose release returns a message and which raises when run."""

    def __init__(self, message: FrostMessage) -> None:
        super().__init__(node="")
        self._message = message

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        raise RuntimeError("boom")

    def release(self, context: ExecutionContext) -> list[FrostMessage]:
        return [self._message]


class TestDefaultAndRunLoop:
    def test_default_release_returns_no_messages(self) -> None:
        class Plain(LocalExecutionNode):
            def __init__(self) -> None:
                super().__init__(node="")

            def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
                return execution_success()

        assert Plain().release(new_context()) == []

    def test_messages_of_release_go_with_the_failure(self) -> None:
        message = FrostMessageBuilder(
            sender="dm"
        ).build_unsubscribe_variable_message(
            target="remote_dm", node="remote/var"
        )
        context = new_context()

        messages = ControlFlow(
            nodes=[Messaging(message)], strict=False
        ).execute(context)

        assert messages == [message]
        assert context.status is ControlFlowStatus.FAILED
        assert context.error is not None
        assert context.error.code is ExecutionErrorCode.UNEXPECTED_ERROR

    def test_strict_mode_does_not_release(self) -> None:
        message = FrostMessageBuilder(
            sender="dm"
        ).build_unsubscribe_variable_message(
            target="remote_dm", node="remote/var"
        )

        with pytest.raises(RuntimeError, match="boom"):
            ControlFlow(nodes=[Messaging(message)], strict=True).execute(
                new_context()
            )


class TestRemoteRelease:
    def test_nothing_sent_nothing_to_clean_up(self) -> None:
        assert remote_wait().release(new_context()) == []

    def test_request_in_flight_is_unsubscribed(self) -> None:
        node = remote_wait()
        context = new_context()
        result = node.execute(context)
        assert result.messages  # the subscribe request
        assert context.active_request is not None

        released = node.release(context)

        assert len(released) == 1
        assert_unsubscribe(released[0], context)

    def test_response_received_is_unsubscribed(self) -> None:
        node = remote_wait()
        context = new_context()
        context.status = ControlFlowStatus.RESPONSE_RECEIVED
        context.active_request = None

        released = node.release(context)

        assert len(released) == 1
        assert_unsubscribe(released[0], context)

    def test_after_the_normal_cleanup_nothing_is_left(self) -> None:
        node = remote_wait()
        context = new_context()
        context.status = ControlFlowStatus.RUNNING
        context.active_request = None

        assert node.release(context) == []

    def test_call_remote_method_has_no_cleanup(self) -> None:
        node = CallRemoteMethodNode(
            method_node="m", remote_id="remote_dm", args=[], kwargs={}
        )
        node.set_message_builder(FrostMessageBuilder(sender="dm"))
        context = new_context()
        node.execute(context)

        assert node.release(context) == []


def waiting_chain() -> tuple[CompositeMethodNode, CompositeMethodNode, Any]:
    node = remote_wait()
    child = CompositeMethodNode(
        id="child", name="child", cfg=ControlFlow(nodes=[node])
    )
    call = CallMethodNode(method_node="child", args=[], kwargs={})
    call.set_ref_node(child)
    parent = CompositeMethodNode(
        id="parent", name="parent", cfg=ControlFlow(nodes=[call])
    )
    return parent, child, call


class TestAbortReturnsMessages:
    def test_abort_context_returns_the_unsubscribe(self) -> None:
        parent, child, call = waiting_chain()
        parent()
        child_id = next(iter(child._contexts))
        child_context = child._get_context(child_id)

        messages = child.abort_context(child_id)

        assert len(messages) == 1
        assert_unsubscribe(messages[0], child_context)
        assert child._contexts == {}

    def test_abort_unknown_context_returns_nothing(self) -> None:
        _, child, _ = waiting_chain()

        assert child.abort_context("nope") == []

    def test_call_node_release_returns_the_callee_messages(self) -> None:
        parent, child, call = waiting_chain()
        parent_id = parent().return_values["@context_id"]
        parent_context = parent._get_context(parent_id)
        child_id = next(iter(child._contexts))
        child_context = child._get_context(child_id)

        messages = call.release(parent_context)

        assert len(messages) == 1
        assert_unsubscribe(messages[0], child_context)
        assert_no_contexts(child)

    def test_chain_of_calls_bubbles_the_message_up(self) -> None:
        parent, child, call = waiting_chain()
        grand_call = CallMethodNode(method_node="parent", args=[], kwargs={})
        grand_call.set_ref_node(parent)
        grandparent = CompositeMethodNode(
            id="grandparent",
            name="grandparent",
            cfg=ControlFlow(nodes=[grand_call]),
        )
        grandparent()
        child_context = child._get_context(next(iter(child._contexts)))

        messages = grandparent.abort_context(next(iter(grandparent._contexts)))

        assert len(messages) == 1
        assert_unsubscribe(messages[0], child_context)
        assert_no_contexts(grandparent, parent, child)
