"""Exceptions raised while completing a composite method (post-call hook)."""

from typing import Any

import pytest

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
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
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import MsgType
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorCode,
    ErrorPayload,
)
from tests.behavior import (
    assert_no_contexts,
    frost_request,
    frost_setup,
    wait_for_nonzero,
)


def boom(ret: dict[str, Any]) -> None:
    raise RuntimeError("boom")


def method(
    name: str,
    nodes: list[ControlFlowNode],
    strict: bool = False,
    post_call: Any = boom,
) -> CompositeMethodNode:
    node = CompositeMethodNode(
        id=name,
        name=name,
        cfg=ControlFlow(nodes=list(nodes), strict=strict),
    )
    if post_call is not None:
        node.post_callback = post_call
    return node


def call(name: str) -> CallMethodNode:
    return CallMethodNode(method_node=name, args=[], kwargs={})


class SetValue(LocalExecutionNode):
    def __init__(self, name: str, value: Any) -> None:
        super().__init__(node="")
        self._name = name
        self._value = value

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        context.set_value(self._name, self._value)
        return execution_success()


class TestSync:
    def test_post_call_raising_fails_the_method(self) -> None:
        m = method("m", [])

        result = m()

        assert result.return_values == {}
        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert result.error.message == (
            "post-call callback raised: RuntimeError: boom"
        )
        assert result.error.node == m.qualified_name
        assert_no_contexts(m)

    def test_building_the_return_values_raising_fails_the_method(self) -> None:
        m = CompositeMethodNode(
            id="m",
            name="m",
            returns=[NumericalVariableNode(name="r", value=0)],
            cfg=ControlFlow(nodes=[SetValue("r", 1)], strict=False),
        )

        def broken(ret: Any) -> dict[str, Any]:
            raise ValueError("cannot build")

        m._build_return_dict = broken  # type: ignore[method-assign]

        result = m()

        assert result.return_values == {}
        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert result.error.message == (
            "the return values could not be built: ValueError: cannot build"
        )
        assert_no_contexts(m)

    def test_strict_reraises_but_still_releases(self) -> None:
        m = method("m", [], strict=True)

        with pytest.raises(RuntimeError, match="boom"):
            m()

        assert_no_contexts(m)


class TestResume:
    def test_post_call_raising_on_resume_fails_the_context(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        wait = wait_for_nonzero(trigger)
        wait.set_ref_node(trigger)
        m = method("m", [wait])
        ctx_id = m().return_values["@context_id"]
        trigger.write(1)

        resumed = m.resume_execution(ctx_id)

        assert resumed.error is not None
        assert resumed.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert m.has_failed(ctx_id)
        assert m._get_context(ctx_id).status is ControlFlowStatus.FAILED
        assert m._completed_results == {}
        m.delete_context(ctx_id)
        assert_no_contexts(m)


class TestNested:
    def test_child_post_call_raising_fails_the_parent(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = method("child", [wait_for_nonzero(trigger)])
        parent = method("parent", [call("child")], post_call=None)
        data_model_nodes = frost_setup(child, parent, variables=(trigger,))
        manager, data_model = data_model_nodes
        started = manager.handle_request(frost_request("dm", "parent"))
        assert isinstance(started, FrostMessage)
        manager.drain_update_messages()

        trigger.write(1)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.ERROR
        assert updates[0].correlation_id == started.correlation_id
        assert isinstance(updates[0].payload, ErrorPayload)
        assert updates[0].payload.error_code is ErrorCode.UNKNOWN
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert trigger.get_subscriptions() == []
        assert_no_contexts(parent, child)

    def test_root_post_call_raising_answers_the_request(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        child = method("child", [wait_for_nonzero(trigger)], post_call=None)
        parent = method("parent", [call("child")])
        manager, data_model = frost_setup(child, parent, variables=(trigger,))
        started = manager.handle_request(frost_request("dm", "parent"))
        assert isinstance(started, FrostMessage)
        manager.drain_update_messages()

        trigger.write(1)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.ERROR
        assert updates[0].correlation_id == started.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(parent, child)

    def test_sync_request_with_raising_post_call_is_answered(self) -> None:
        m = method("m", [])
        manager, data_model = frost_setup(m)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.ERROR
        assert manager._running_methods == {}
        assert data_model._contexts == {}


class TestFrostSecondLayer:
    def test_strict_exception_still_answers_and_releases_the_request(
        self,
    ) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        m = method("m", [wait_for_nonzero(trigger)], strict=True)
        manager, data_model = frost_setup(m, variables=(trigger,))
        started = manager.handle_request(frost_request("dm", "m"))
        assert isinstance(started, FrostMessage)
        manager.drain_update_messages()

        # The strict re-raise escapes the subscription callback (and so the
        # write that triggered it), but the request is answered first.
        with pytest.raises(RuntimeError, match="boom"):
            trigger.write(1)

        updates = manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.ERROR
        assert updates[0].correlation_id == started.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(m)
