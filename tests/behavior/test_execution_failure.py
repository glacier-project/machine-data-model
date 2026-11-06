"""Tests for the FAILURE outcome of control flow nodes and its consumers."""

from collections.abc import Callable
from typing import Any
import uuid

import pytest

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    NodeStatus,
    execution_error,
    execution_failure,
    execution_success,
)
from machine_data_model.behavior.execution_context import (
    ControlFlowStatus,
    ExecutionContext,
)
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
    ContextNotFoundError,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MethodMsgName,
    MsgNamespace,
    MsgType,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorCode,
    ErrorMessages,
    ErrorPayload,
    MethodPayload,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)

ERROR = ExecutionError(
    ExecutionErrorCode.PRECONDITION_NOT_MET, "mode must be 2", "stub"
)


class StubNode(LocalExecutionNode):
    """Node returning a scripted result, recording how often it ran."""

    def __init__(self, make: Callable[[], ExecutionNodeResult]) -> None:
        super().__init__(node="")
        self._make = make
        self.runs = 0

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        self.runs += 1
        return self._make()


def failing_stub(error: ExecutionError = ERROR) -> StubNode:
    return StubNode(lambda: execution_error(error))


def composite(name: str, nodes: list[ControlFlowNode]) -> CompositeMethodNode:
    return CompositeMethodNode(
        id=name, name=name, cfg=ControlFlow(nodes=list(nodes))
    )


def wait_for_nonzero(trigger: NumericalVariableNode) -> WaitConditionNode:
    node = WaitConditionNode(
        variable_node=trigger.name,
        rhs=0,
        op=WaitConditionOperator.NE,
    )
    node.set_ref_node(trigger)
    return node


def new_context() -> ExecutionContext:
    return ExecutionContext(str(uuid.uuid4()))


def assert_no_contexts(*methods: CompositeMethodNode) -> None:
    for method in methods:
        assert method._contexts == {}, method.name
        assert method._completed_results == {}, method.name


class TestExecutionNodeResult:
    def test_bool_true_is_success(self) -> None:
        result = ExecutionNodeResult(True)

        assert result.status is NodeStatus.SUCCESS
        assert result.success
        assert not result.failed
        assert result.error is None
        assert result.messages == []

    def test_bool_false_is_running(self) -> None:
        result = ExecutionNodeResult(False)

        assert result.status is NodeStatus.RUNNING
        assert not result.success
        assert not result.failed

    def test_positional_messages_still_work(self) -> None:
        msg = object()

        result = ExecutionNodeResult(False, [msg])  # type: ignore[list-item]

        assert result.messages == [msg]

    def test_helpers(self) -> None:
        assert execution_success().status is NodeStatus.SUCCESS
        assert execution_failure().status is NodeStatus.RUNNING
        failure = execution_failure()
        assert not failure.success and not failure.failed

    def test_execution_error_carries_error_and_messages(self) -> None:
        msg = object()

        result = execution_error(ERROR, [msg])  # type: ignore[list-item]

        assert result.status is NodeStatus.FAILURE
        assert result.failed
        assert not result.success
        assert result.error is ERROR
        assert result.messages == [msg]

    def test_failure_requires_error_and_only_failure(self) -> None:
        with pytest.raises(ValueError):
            ExecutionNodeResult(NodeStatus.FAILURE)
        with pytest.raises(ValueError):
            ExecutionNodeResult(NodeStatus.SUCCESS, None, ERROR)
        with pytest.raises(ValueError):
            ExecutionNodeResult(False, None, ERROR)

    def test_success_is_read_only(self) -> None:
        result = ExecutionNodeResult(True)

        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestExecutionContextFail:
    def test_fail_sets_status_error_and_clears_request(self) -> None:
        context = new_context()
        context.active_request = "req"

        context.fail(ERROR)

        assert context.status is ControlFlowStatus.FAILED
        assert context.error is ERROR
        assert not context.active_request
        assert not context.is_active()

    def test_error_is_none_by_default(self) -> None:
        assert new_context().error is None


class TestRunLoop:
    def test_failure_fails_context_and_stops_the_loop(self) -> None:
        first = StubNode(execution_success)
        failing = failing_stub()
        later = StubNode(execution_success)
        cfg = ControlFlow(nodes=[first, failing, later])
        context = new_context()

        messages = cfg.execute(context)

        assert messages == []
        assert (first.runs, failing.runs, later.runs) == (1, 1, 0)
        assert context.status is ControlFlowStatus.FAILED
        assert context.error is ERROR
        assert context.get_pc() == 1
        assert not context.is_active()

    def test_failure_messages_are_returned(self) -> None:
        msg = object()
        node = StubNode(
            lambda: execution_error(ERROR, [msg])  # type: ignore[list-item]
        )

        messages = ControlFlow(nodes=[node]).execute(new_context())

        assert messages == [msg]

    def test_running_is_not_a_failure(self) -> None:
        node = StubNode(execution_failure)
        context = new_context()

        ControlFlow(nodes=[node]).execute(context)

        assert context.is_active()
        assert context.error is None
        assert context.get_pc() == 0

    def test_success_completes(self) -> None:
        context = new_context()

        ControlFlow(nodes=[StubNode(execution_success)]).execute(context)

        assert context.status is ControlFlowStatus.COMPLETED
        assert context.error is None


class TestCompositeFailure:
    def test_sync_failure(self) -> None:
        post_calls: list[dict[str, Any]] = []
        method = composite("m", [failing_stub()])
        method.post_callback = post_calls.append

        result = method()

        assert result.return_values == {}
        assert result.error is ERROR
        assert post_calls == []
        assert_no_contexts(method)

    def test_terminate_execution_on_failed_context(self) -> None:
        method = composite("m", [failing_stub()])
        context = method._create_context()
        method.cfg.execute(context)

        assert method._terminate_execution(context) == {}
        assert method._completed_results == {}

    def test_failure_after_wait_is_reported_on_resume(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        method = composite("m", [wait_for_nonzero(trigger), failing_stub()])
        method.post_callback = lambda ret: pytest.fail("post_call called")

        started = method()
        ctx_id = started.return_values["@context_id"]
        assert started.error is None
        assert not method.has_failed(ctx_id)
        assert method.get_error(ctx_id) is None

        trigger.write(1)
        resumed = method.resume_execution(ctx_id)

        assert resumed.return_values == {}
        assert resumed.error is ERROR
        assert method.is_terminated(ctx_id)
        assert method.has_failed(ctx_id)
        assert method.get_error(ctx_id) is ERROR
        assert method.get_completed_return_values(ctx_id) is None
        assert trigger.get_subscriptions() == []
        method.delete_context(ctx_id)
        assert_no_contexts(method)

    def test_is_terminated_covers_failed_and_completed(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        method = composite("m", [wait_for_nonzero(trigger)])
        ctx_id = method().return_values["@context_id"]

        assert not method.is_terminated(ctx_id)
        assert not method.has_failed(ctx_id)
        trigger.write(1)
        method.resume_execution(ctx_id)
        assert method.is_terminated(ctx_id)
        assert not method.has_failed(ctx_id)


def build_nested(
    child_nodes: list[ControlFlowNode],
) -> tuple[CompositeMethodNode, CompositeMethodNode]:
    child = composite("child", child_nodes)
    call = CallMethodNode(method_node="child", args=[], kwargs={})
    call.set_ref_node(child)
    parent = composite("parent", [call])
    return parent, child


class TestNestedFailure:
    def test_child_fails_on_first_call(self) -> None:
        parent, child = build_nested([failing_stub()])

        result = parent()

        assert result.return_values == {}
        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert result.error.message == "/child: mode must be 2"
        assert result.error.node == "/child"
        assert_no_contexts(parent, child)

    def test_child_fails_after_a_wait(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        parent, child = build_nested(
            [wait_for_nonzero(trigger), failing_stub()]
        )
        started = parent()
        parent_ctx_id = started.return_values["@context_id"]
        parent_ctx = parent._get_context(parent_ctx_id)
        assert parent_ctx.has_value("call_method_pending_0")
        assert len(child._contexts) == 1

        trigger.write(1)
        child_ctx_id = next(iter(child._contexts))
        child.resume_execution(child_ctx_id)

        assert parent.has_failed(parent_ctx_id)
        error = parent.get_error(parent_ctx_id)
        assert error is not None
        assert error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert error.message.startswith("/child: ")
        assert parent_ctx.status is ControlFlowStatus.FAILED
        assert not parent_ctx.has_value("call_method_pending_0")
        assert trigger.get_subscriptions() == []
        assert child._contexts == {}
        assert child._completed_results == {}
        # The parent context stays until its consumer collects the error.
        parent.delete_context(parent_ctx_id)
        assert_no_contexts(parent, child)

    def test_explicit_parent_resume_sees_child_failure(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        parent, child = build_nested(
            [wait_for_nonzero(trigger), failing_stub()]
        )
        parent_ctx_id = parent().return_values["@context_id"]
        child_ctx_id = next(iter(child._contexts))
        trigger.write(1)
        # Mark the child as already notified so only the explicit resume of
        # the parent observes the failure.
        child._notified_parent_contexts.add(child_ctx_id)
        child.resume_execution(child_ctx_id)
        assert child.has_failed(child_ctx_id)

        resumed = parent.resume_execution(parent_ctx_id)

        assert resumed.error is not None
        assert resumed.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert parent.has_failed(parent_ctx_id)
        parent.delete_context(parent_ctx_id)
        assert_no_contexts(parent, child)

    def test_grandparent_receives_the_error_code(self) -> None:
        child = composite("child", [failing_stub()])
        call_child = CallMethodNode(method_node="child", args=[], kwargs={})
        call_child.set_ref_node(child)
        parent = composite("parent", [call_child])
        call_parent = CallMethodNode(method_node="parent", args=[], kwargs={})
        call_parent.set_ref_node(parent)
        grandparent = composite("grandparent", [call_parent])

        result = grandparent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert result.error.message == "/parent: /child: mode must be 2"
        assert_no_contexts(grandparent, parent, child)


class TestContextRelease:
    def test_sync_completion_releases_context(self) -> None:
        method = composite("m", [StubNode(execution_success)])

        result = method()

        assert result.error is None
        assert_no_contexts(method)

    def test_pending_composite_keeps_exactly_one_context(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        method = composite("m", [wait_for_nonzero(trigger)])

        ctx_id = method().return_values["@context_id"]
        assert list(method._contexts) == [ctx_id]
        method.resume_execution(ctx_id)
        assert list(method._contexts) == [ctx_id]

        trigger.write(1)
        method.resume_execution(ctx_id)
        # Resume does not release: the consumer collects, then deletes.
        assert list(method._contexts) == [ctx_id]
        assert method.get_completed_return_values(ctx_id) == {}
        method.delete_context(ctx_id)
        assert_no_contexts(method)

    def test_nested_completion_is_collected_by_the_parent(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        parent, child = build_nested([wait_for_nonzero(trigger)])
        parent_ctx_id = parent().return_values["@context_id"]
        child_ctx_id = next(iter(child._contexts))

        trigger.write(1)
        child.resume_execution(child_ctx_id)

        assert child._contexts == {}
        assert child._completed_results == {}
        assert not parent.has_failed(parent_ctx_id)
        assert parent.is_terminated(parent_ctx_id)
        parent.delete_context(parent_ctx_id)
        assert_no_contexts(parent, child)


def frost_request(target: str, node: str) -> FrostMessage:
    return FrostMessage(
        sender="client",
        target=target,
        identifier=str(uuid.uuid4()),
        header=FrostHeader(
            type=MsgType.REQUEST,
            namespace=MsgNamespace.METHOD,
            msg_name=MethodMsgName.INVOKE,
        ),
        payload=MethodPayload(node=node),
    )


def frost_setup(
    *methods: CompositeMethodNode,
    variables: tuple[NumericalVariableNode, ...] = (),
) -> tuple[FrostProtocolMng, DataModel]:
    data_model = DataModel(name="dm")
    for variable in variables:
        data_model.root.add_child(variable)
    for method in methods:
        data_model.root.add_child(method)
    data_model._register_nodes(data_model.root)
    return FrostProtocolMng(data_model), data_model


class TestFrost:
    def test_sync_failure_gives_error_response(self) -> None:
        method = composite("m", [failing_stub()])
        manager, _ = frost_setup(method)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.ERROR
        assert isinstance(response.payload, ErrorPayload)
        assert response.payload.error_code is ErrorCode.NOT_ALLOWED
        assert response.payload.error_message == (
            f"{ErrorMessages.PRECONDITION_NOT_MET.value}: mode must be 2"
        )
        assert manager._running_methods == {}
        assert_no_contexts(method)

    @pytest.mark.parametrize(
        "code, expected_code, expected_message",
        [
            (
                ExecutionErrorCode.PRECONDITION_NOT_MET,
                ErrorCode.NOT_ALLOWED,
                ErrorMessages.PRECONDITION_NOT_MET,
            ),
            (
                ExecutionErrorCode.NO_DATA,
                ErrorCode.NOT_ALLOWED,
                ErrorMessages.NO_DATA,
            ),
            (
                ExecutionErrorCode.TIMEOUT,
                ErrorCode.UNKNOWN,
                ErrorMessages.TIMEOUT,
            ),
            (
                ExecutionErrorCode.INVALID_CONFIGURATION,
                ErrorCode.BAD_REQUEST,
                ErrorMessages.BAD_REQUEST,
            ),
            (
                ExecutionErrorCode.REMOTE_ERROR,
                ErrorCode.UNKNOWN,
                ErrorMessages.REMOTE_ERROR,
            ),
        ],
    )
    def test_error_code_mapping(
        self,
        code: ExecutionErrorCode,
        expected_code: ErrorCode,
        expected_message: ErrorMessages,
    ) -> None:
        method = composite("m", [failing_stub(ExecutionError(code, "x"))])
        manager, _ = frost_setup(method)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert isinstance(response.payload, ErrorPayload)
        assert response.payload.error_code is expected_code
        assert response.payload.error_message == f"{expected_message.value}: x"

    def test_failure_after_wait_is_sent_as_update_error(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        method = composite("m", [wait_for_nonzero(trigger), failing_stub()])
        manager, _ = frost_setup(method, variables=(trigger,))
        started = manager.handle_request(frost_request("dm", "m"))
        assert isinstance(started, FrostMessage)
        assert started.header.type is MsgType.RESPONSE
        assert len(manager._running_methods) == 1
        manager.clear_update_messages()

        trigger.write(1)

        updates = manager.get_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.ERROR
        assert updates[0].target == "client"
        assert updates[0].correlation_id == started.correlation_id
        assert isinstance(updates[0].payload, ErrorPayload)
        assert updates[0].payload.error_code is ErrorCode.NOT_ALLOWED
        assert manager._running_methods == {}
        assert_no_contexts(method)
        assert trigger.get_subscriptions() == []

    def test_completed_path_is_unchanged(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        method = composite("m", [wait_for_nonzero(trigger)])
        manager, _ = frost_setup(method, variables=(trigger,))
        started = manager.handle_request(frost_request("dm", "m"))
        assert isinstance(started, FrostMessage)
        manager.clear_update_messages()

        trigger.write(1)

        updates = manager.get_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.RESPONSE
        assert isinstance(updates[0].payload, MethodPayload)
        assert manager._running_methods == {}
        assert_no_contexts(method)

    def test_sync_completion_response_is_unchanged(self) -> None:
        method = composite("m", [StubNode(execution_success)])
        manager, _ = frost_setup(method)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.RESPONSE
        assert_no_contexts(method)

    def test_other_error_messages_keep_bad_request_code(self) -> None:
        manager, _ = frost_setup()

        response = manager.handle_request(frost_request("dm", "missing"))

        assert isinstance(response, FrostMessage)
        assert isinstance(response.payload, ErrorPayload)
        assert response.payload.error_code is ErrorCode.BAD_REQUEST
        assert response.payload.error_message is ErrorMessages.NODE_NOT_FOUND


class TestTerminalContextIsFinal:
    def test_double_resume_of_failed_context_stays_failed(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        failing = failing_stub()
        method = composite("m", [wait_for_nonzero(trigger), failing])
        post_calls: list[dict[str, Any]] = []
        method.post_callback = post_calls.append
        ctx_id = method().return_values["@context_id"]
        trigger.write(1)
        first = method.resume_execution(ctx_id)
        assert failing.runs == 1

        second = method.resume_execution(ctx_id)

        assert first.error is ERROR
        assert second.error is ERROR
        assert second.return_values == {}
        assert second.messages == []
        assert failing.runs == 1
        context = method._get_context(ctx_id)
        assert context.status is ControlFlowStatus.FAILED
        assert context.error is ERROR
        assert method._completed_results == {}
        assert post_calls == []

    def test_double_resume_of_completed_context_is_unchanged(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        result = NumericalVariableNode(id="r", name="r", value=0)
        method = CompositeMethodNode(
            id="m",
            name="m",
            returns=[result],
            cfg=ControlFlow(nodes=[wait_for_nonzero(trigger)]),
        )
        post_calls: list[dict[str, Any]] = []
        method.post_callback = post_calls.append
        context = method._create_context()
        context.set_value("r", 7)
        method.cfg.execute(context)
        trigger.write(1)
        first = method.resume_execution(context.id())
        assert first.return_values == {"r": 7}

        second = method.resume_execution(context.id())

        assert second.return_values == {"r": 7}
        assert second.error is None
        assert second.messages == []
        assert context.status is ControlFlowStatus.COMPLETED
        assert len(post_calls) == 1

    def test_run_loop_does_not_touch_terminal_context(self) -> None:
        node = StubNode(execution_success)
        context = new_context()
        context.fail(ERROR)

        messages = ControlFlow(nodes=[node]).execute(context)

        assert messages == []
        assert node.runs == 0
        assert context.status is ControlFlowStatus.FAILED

    def test_deactivate_does_not_overwrite_failure(self) -> None:
        context = new_context()
        context.fail(ERROR)

        context.deactivate()

        assert context.status is ControlFlowStatus.FAILED

    def test_resume_unknown_context_raises_value_error(self) -> None:
        method = composite("m", [StubNode(execution_success)])

        with pytest.raises(ValueError):
            method.resume_execution("missing")


class TestResultImmutability:
    def test_status_and_error_are_read_only(self) -> None:
        result = execution_error(ERROR)

        with pytest.raises(AttributeError):
            result.status = NodeStatus.SUCCESS  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.error = None  # type: ignore[misc]
        assert result.failed


class TestErrorOrigin:
    def test_origin_defaults_to_none(self) -> None:
        assert ExecutionError(ExecutionErrorCode.TIMEOUT, "t").origin is None

    def test_chain_keeps_the_root_cause(self) -> None:
        c = composite("c", [failing_stub()])
        call_c = CallMethodNode(method_node="c", args=[], kwargs={})
        call_c.set_ref_node(c)
        b = composite("b", [call_c])
        call_b = CallMethodNode(method_node="b", args=[], kwargs={})
        call_b.set_ref_node(b)
        a = composite("a", [call_b])

        error = a().error

        assert error is not None
        assert error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert error.message == "/b: /c: mode must be 2"
        assert error.node == "/b"
        # Root cause: the node of the original error, not an intermediate.
        assert error.origin == "stub"

    def test_templated_callee_uses_the_resolved_path(self) -> None:
        child = composite("child", [failing_stub()])
        call = CallMethodNode(method_node="${callee}", args=[], kwargs={})
        parent = composite("parent", [call])
        data_model = DataModel(name="dm")
        data_model.root.add_child(child)
        data_model.root.add_child(parent)
        data_model._register_nodes(data_model.root)
        context = ExecutionContext(str(uuid.uuid4()))
        context.set_value("callee", child.id)

        result = call.execute(context)

        assert result.failed
        assert result.error is not None
        assert "${" not in result.error.message
        assert result.error.node == child.qualified_name
        assert result.error.message.startswith(f"{child.qualified_name}: ")
        assert result.error.origin == "stub"


class TestErrorMapping:
    def test_every_code_has_a_response_entry(self) -> None:
        from machine_data_model.protocols.frost_v1 import frost_protocol_mng

        mapping = frost_protocol_mng._EXECUTION_ERROR_RESPONSES

        assert set(mapping) == set(ExecutionErrorCode)
        messages = [message for _, message in mapping.values()]
        assert ErrorMessages.REMOTE_ERROR in messages


class TestNestedParentNotification:
    def test_notify_survives_a_deleted_parent_context(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        parent, child = build_nested([wait_for_nonzero(trigger)])
        parent_ctx_id = parent().return_values["@context_id"]
        child_ctx_id = next(iter(child._contexts))
        parent.delete_context(parent_ctx_id)
        trigger.write(1)

        result = child.resume_execution(child_ctx_id)

        assert result.error is None
        assert child.is_terminated(child_ctx_id)

    def test_raising_notification_does_not_leak_the_context(self) -> None:
        method = composite("m", [StubNode(execution_success)])

        def boom(context: ExecutionContext) -> list[Any]:
            raise RuntimeError("boom")

        method._notify_nested_parent = boom  # type: ignore[method-assign]

        with pytest.raises(RuntimeError):
            method()

        assert_no_contexts(method)


class TestFrostNestedLimit:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "pre-existing limit: under Frost a nested child composite that "
            "waits is never resumed, its subscriber id (child context id) is "
            "not in FrostProtocolMng._running_methods"
        ),
    )
    def test_nested_waiting_child_is_resumed_by_frost(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        parent, child = build_nested([wait_for_nonzero(trigger)])
        manager, _ = frost_setup(child, parent, variables=(trigger,))
        started = manager.handle_request(frost_request("dm", "parent"))
        assert isinstance(started, FrostMessage)
        manager.clear_update_messages()

        trigger.write(1)

        # The parent invocation must complete: a method response is sent and
        # the invocation is no longer running. Today only a plain variable
        # update for the child context id is produced.
        updates = manager.get_update_messages()
        assert any(isinstance(u.payload, MethodPayload) for u in updates)
        assert manager._running_methods == {}


class RaisingNode(LocalExecutionNode):
    """Node raising the given exception when executed."""

    def __init__(self, exc: Exception) -> None:
        super().__init__(node="")
        self._exc = exc

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        raise self._exc


class TestParentErrorsPropagate:
    @pytest.mark.parametrize(
        "exc",
        [KeyError("missing"), ValueError("bad"), ContextNotFoundError("x")],
    )
    def test_error_in_parent_cfg_propagates_out_of_child_resume(
        self, exc: Exception
    ) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = composite("child", [wait_for_nonzero(trigger)])
        call = CallMethodNode(method_node="child", args=[], kwargs={})
        call.set_ref_node(child)
        parent = composite("parent", [call, RaisingNode(exc)])
        parent()
        child_ctx_id = next(iter(child._contexts))
        trigger.write(1)

        with pytest.raises(type(exc)):
            child.resume_execution(child_ctx_id)

    def test_unknown_parent_id_is_ignored(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        parent, child = build_nested([wait_for_nonzero(trigger)])
        parent_ctx_id = parent().return_values["@context_id"]
        child_ctx_id = next(iter(child._contexts))
        parent.delete_context(parent_ctx_id)
        trigger.write(1)

        result = child.resume_execution(child_ctx_id)

        assert result.error is None

    def test_context_not_found_is_a_value_error(self) -> None:
        method = composite("m", [StubNode(execution_success)])

        with pytest.raises(ContextNotFoundError) as info:
            method.delete_context("nope")
        with pytest.raises(ContextNotFoundError):
            method.resume_execution("nope")

        assert isinstance(info.value, ValueError)
        assert info.value.context_id == "nope"


class TestIdempotentResumeCopy:
    def test_completed_result_is_a_copy(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        result = NumericalVariableNode(id="r", name="r", value=0)
        method = CompositeMethodNode(
            id="m",
            name="m",
            returns=[result],
            cfg=ControlFlow(nodes=[wait_for_nonzero(trigger)]),
        )
        context = method._create_context()
        context.set_value("r", 7)
        method.cfg.execute(context)
        trigger.write(1)
        method.resume_execution(context.id())

        again = method.resume_execution(context.id())
        again.return_values["r"] = 999
        again.return_values["extra"] = 1

        assert method.get_completed_return_values(context.id()) == {"r": 7}
        assert method.resume_execution(context.id()).return_values == {"r": 7}
