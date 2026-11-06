"""Tests for unexpected exceptions in nodes becoming FAILURE."""

import logging
import subprocess
import sys
from typing import Any
import uuid

import pytest

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ExecutionNodeResult,
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


class Boom(LocalExecutionNode):
    """Node raising an exception, recording whether it was released."""

    def __init__(self, exc: BaseException) -> None:
        super().__init__(node="")
        self._exc = exc
        self.released = 0

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        raise self._exc

    def release(self, context: ExecutionContext) -> None:
        self.released += 1


class Ok(LocalExecutionNode):
    def __init__(self) -> None:
        super().__init__(node="")
        self.runs = 0

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        self.runs += 1
        return execution_success()


def new_context() -> ExecutionContext:
    return ExecutionContext(str(uuid.uuid4()))


class TestRunLoop:
    @pytest.mark.parametrize(
        "exc", [KeyError("k"), ValueError("v"), AssertionError("a")]
    )
    def test_exception_becomes_failure(self, exc: Exception) -> None:
        boom = Boom(exc)
        later = Ok()
        context = new_context()

        messages = ControlFlow(strict=False, nodes=[boom, later]).execute(
            context
        )

        assert messages == []
        assert context.status is ControlFlowStatus.FAILED
        assert context.error is not None
        assert context.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert context.error.message == f"{type(exc).__name__}: {exc}"
        assert context.error.node == "Boom"
        assert context.get_pc() == 0
        assert later.runs == 0
        assert boom.released == 1

    def test_exception_is_logged_with_traceback(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR):
            ControlFlow(strict=False, nodes=[Boom(ValueError("v"))]).execute(
                new_context()
            )

        records = [r for r in caplog.records if r.exc_info is not None]
        assert len(records) == 1
        assert "Unexpected error" in records[0].getMessage()

    @pytest.mark.parametrize("exc", [KeyboardInterrupt(), SystemExit(1)])
    def test_base_exception_still_propagates(self, exc: BaseException) -> None:
        context = new_context()

        with pytest.raises(type(exc)):
            ControlFlow(strict=False, nodes=[Boom(exc)]).execute(context)

        assert context.is_active()

    def test_strict_mode_reraises(self) -> None:
        context = new_context()

        with pytest.raises(KeyError):
            ControlFlow(nodes=[Boom(KeyError("k"))], strict=True).execute(
                context
            )

        assert context.is_active()

    def test_failing_release_is_logged_not_raised(self) -> None:
        class BadRelease(Boom):
            def release(self, context: ExecutionContext) -> None:
                raise RuntimeError("release failed")

        context = new_context()

        ControlFlow(strict=False, nodes=[BadRelease(ValueError("v"))]).execute(
            context
        )

        assert context.error is not None
        assert context.error.code is ExecutionErrorCode.UNEXPECTED_ERROR

    def test_composite_returns_error_result(self) -> None:
        method = CompositeMethodNode(
            id="m",
            name="m",
            cfg=ControlFlow(strict=False, nodes=[Boom(KeyError("k"))]),
        )

        result = method()

        assert result.return_values == {}
        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert method._contexts == {}


class TestRelease:
    def test_wait_node_releases_subscription_and_keys(self) -> None:
        variable = NumericalVariableNode(id="v", name="v", value=20)
        wait = WaitConditionNode(
            variable_node="v",
            rhs="${limit}",
            op=WaitConditionOperator.LT,
        )
        wait.set_ref_node(variable)
        context = new_context()
        context.set_value("limit", 10)
        cfg = ControlFlow(strict=False, nodes=[wait])
        cfg.execute(context)
        assert len(variable.get_subscriptions()) == 1
        assert any(k.startswith("wait_") for k in context.locals())

        # The condition can no longer be evaluated: comparing with a string.
        context.set_value("limit", "abc")
        cfg.execute(context)

        assert context.status is ControlFlowStatus.FAILED
        assert context.error is not None
        assert context.error.code is ExecutionErrorCode.UNEXPECTED_ERROR
        assert context.error.message.startswith("TypeError")
        assert variable.get_subscriptions() == []
        assert not any(k.startswith("wait_") for k in context.locals())

    def test_call_node_release_aborts_the_pending_callee(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        wait = WaitConditionNode(
            variable_node="t", rhs=0, op=WaitConditionOperator.NE
        )
        wait.set_ref_node(trigger)
        child = CompositeMethodNode(
            id="child",
            name="child",
            cfg=ControlFlow(strict=False, nodes=[wait]),
        )
        call = CallMethodNode(method_node="child", args=[], kwargs={})
        call.set_ref_node(child)
        parent = CompositeMethodNode(
            id="parent",
            name="parent",
            cfg=ControlFlow(strict=False, nodes=[call]),
        )
        parent_ctx_id = parent().return_values["@context_id"]
        parent_ctx = parent._get_context(parent_ctx_id)
        assert len(child._contexts) == 1
        assert len(trigger.get_subscriptions()) == 1

        call.release(parent_ctx)

        assert not parent_ctx.has_value("call_method_pending_0")
        assert child._contexts == {}
        assert trigger.get_subscriptions() == []

    def test_abort_unknown_context_is_ignored(self) -> None:
        method = CompositeMethodNode(id="m", name="m")

        method.abort_context("missing")


class TestFrost:
    def test_response_carries_no_exception_text(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        secret = "/etc/secret/path"
        method = CompositeMethodNode(
            id="m",
            name="m",
            cfg=ControlFlow(strict=False, nodes=[Boom(KeyError(secret))]),
        )
        data_model = DataModel(name="dm")
        data_model.root.add_child(method)
        data_model._register_nodes(data_model.root)
        manager = FrostProtocolMng(data_model)
        request = FrostMessage(
            sender="client",
            target="dm",
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node="m"),
        )

        with caplog.at_level(logging.ERROR):
            response = manager.handle_request(request)

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.ERROR
        assert isinstance(response.payload, ErrorPayload)
        assert response.payload.error_code is ErrorCode.UNKNOWN
        assert (
            response.payload.error_message
            == ErrorMessages.UNEXPECTED_ERROR.value
        )
        assert secret not in response.payload.error_message
        # The detail goes to the log together with the correlation id.
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert secret in text
        assert str(request.correlation_id) in text


def test_drain_update_messages_is_atomic_swap() -> None:
    data_model = DataModel(name="dm")
    manager = FrostProtocolMng(data_model)
    sentinel: Any = object()
    manager._update_messages.append(sentinel)
    live = manager._update_messages

    drained = manager.drain_update_messages()

    assert drained == [sentinel]
    assert drained is live
    assert manager.get_update_messages() == []
    assert manager.drain_update_messages() == []


class TestStrictResolvedAtExecuteTime:
    def test_graph_built_before_the_default_changed_follows_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ControlFlow, "default_strict", False)
        cfg = ControlFlow(nodes=[Boom(KeyError("k"))])
        before = cfg.strict

        monkeypatch.setattr(ControlFlow, "default_strict", True)

        after = cfg.strict
        assert (before, after) == (False, True)
        with pytest.raises(KeyError):
            cfg.execute(new_context())

    def test_explicit_value_wins_over_the_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ControlFlow, "default_strict", True)
        cfg = ControlFlow(nodes=[Boom(KeyError("k"))], strict=False)
        context = new_context()

        cfg.execute(context)

        assert cfg.strict is False
        assert context.status is ControlFlowStatus.FAILED

    def test_setting_none_follows_the_default_again(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = ControlFlow(nodes=[], strict=False)

        cfg.strict = None
        monkeypatch.setattr(ControlFlow, "default_strict", True)

        assert cfg.strict is True

    def test_production_default_is_not_strict(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "from machine_data_model.behavior.control_flow import "
                "ControlFlow; assert ControlFlow.default_strict is False; "
                "assert ControlFlow().strict is False",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr


class TestTerminalStatesAreFinal:
    def test_fail_on_a_completed_context_raises(self) -> None:
        context = new_context()
        context.deactivate()

        with pytest.raises(ValueError):
            context.fail(ExecutionError(ExecutionErrorCode.TIMEOUT, "t"))

        assert context.status is ControlFlowStatus.COMPLETED
        assert context.error is None

    def test_fail_on_a_failed_context_keeps_the_first_error(self) -> None:
        context = new_context()
        first = ExecutionError(ExecutionErrorCode.TIMEOUT, "first")
        context.fail(first)

        with pytest.raises(ValueError):
            context.fail(ExecutionError(ExecutionErrorCode.NO_DATA, "second"))

        assert context.error is first

    def test_reject_completion_only_from_completed(self) -> None:
        error = ExecutionError(ExecutionErrorCode.INVALID_CONFIGURATION, "x")
        active = new_context()
        failed = new_context()
        failed.fail(error)
        completed = new_context()
        completed.deactivate()

        with pytest.raises(ValueError):
            active.reject_completion(error)
        with pytest.raises(ValueError):
            failed.reject_completion(error)
        completed.reject_completion(error)

        assert active.is_active()
        assert completed.status is ControlFlowStatus.FAILED
        assert completed.error is error


class Reentrant(LocalExecutionNode):
    """Node whose context is terminated while it runs, then it returns."""

    def __init__(
        self,
        terminate: Any,
        result: ExecutionNodeResult,
    ) -> None:
        super().__init__(node="")
        self._terminate = terminate
        self._result = result

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        self._terminate(context)
        return self._result


class TestReentrantTermination:
    def test_failure_after_reentrant_completion_does_not_fail(self) -> None:
        msg: Any = object()
        node = Reentrant(
            lambda ctx: ctx.deactivate(),
            execution_error(
                ExecutionError(ExecutionErrorCode.TIMEOUT, "late"), [msg]
            ),
        )
        later = Ok()
        context = new_context()

        messages = ControlFlow(nodes=[node, later]).execute(context)

        assert messages == [msg]
        assert context.status is ControlFlowStatus.COMPLETED
        assert context.error is None
        assert later.runs == 0

    def test_success_after_reentrant_completion_stops_the_loop(self) -> None:
        node = Reentrant(lambda ctx: ctx.deactivate(), execution_success())
        later = Ok()
        context = new_context()

        ControlFlow(nodes=[node, later]).execute(context)

        assert context.status is ControlFlowStatus.COMPLETED
        assert context.get_pc() == 0
        assert later.runs == 0

    def test_reentrant_failure_is_kept_when_the_node_returns_running(
        self,
    ) -> None:
        first = ExecutionError(ExecutionErrorCode.NO_DATA, "first")
        node = Reentrant(lambda ctx: ctx.fail(first), execution_failure())
        context = new_context()

        ControlFlow(nodes=[node]).execute(context)

        assert context.status is ControlFlowStatus.FAILED
        assert context.error is first

    def test_reentrant_failure_wins_over_a_later_failure(self) -> None:
        first = ExecutionError(ExecutionErrorCode.NO_DATA, "first")
        node = Reentrant(
            lambda ctx: ctx.fail(first),
            execution_error(ExecutionError(ExecutionErrorCode.TIMEOUT, "2nd")),
        )
        context = new_context()

        ControlFlow(nodes=[node]).execute(context)

        assert context.error is first

    def test_no_second_trace_end_event(self) -> None:
        from machine_data_model.tracing import (
            TraceEventType,
            TraceLevel,
            clear_traces,
            get_global_collector,
            set_global_trace_level,
        )

        clear_traces()
        set_global_trace_level(TraceLevel.FULL)
        try:
            node = Reentrant(
                lambda ctx: ctx.deactivate(),
                execution_error(
                    ExecutionError(ExecutionErrorCode.TIMEOUT, "x")
                ),
            )
            ControlFlow(nodes=[node]).execute(new_context())

            ends = get_global_collector().get_events(
                TraceEventType.CONTROL_FLOW_END
            )
            assert ends == []
        finally:
            set_global_trace_level(TraceLevel.NONE)
            clear_traces()
