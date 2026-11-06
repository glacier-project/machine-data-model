"""Remote Frost ERROR messages reach the context that sent the request."""

from dataclasses import replace
import logging

import pytest

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import ControlFlowNode
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
)
from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
    ReadRemoteVariableNode,
    RemoteExecutionNode,
    WaitRemoteEventNode,
    WriteRemoteVariableNode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MethodMsgName,
    MsgName,
    MsgNamespace,
    MsgType,
    VariableMsgName,
)
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
    assert_no_contexts,
    frost_request,
    frost_setup,
    new_context,
    wait_for_nonzero,
)

SECRET = "internal path /etc/plant/secret.yml"


def composite(name: str, nodes: list[ControlFlowNode]) -> CompositeMethodNode:
    return CompositeMethodNode(
        id=name, name=name, cfg=ControlFlow(nodes=list(nodes))
    )


def call(name: str) -> CallMethodNode:
    return CallMethodNode(method_node=name, args=[], kwargs={})


def remote_call() -> CallRemoteMethodNode:
    return CallRemoteMethodNode(
        method_node="remote_method", remote_id="remote_dm", args=[], kwargs={}
    )


def remote_error(
    request: FrostMessage,
    sender: str = "remote_dm",
    text: str = SECRET,
) -> FrostMessage:
    message = FrostMessageBuilder(sender=sender).build_error_message(
        message=request,
        error_code=ErrorCode.NOT_ALLOWED,
        error_message=text,
    )
    return message


def start(
    *composites: CompositeMethodNode, root: str
) -> tuple[FrostProtocolMng, DataModel, FrostMessage, FrostMessage]:
    manager, data_model = frost_setup(*composites)
    started = manager.handle_request(frost_request("dm", root))
    assert isinstance(started, FrostMessage)
    sent = [
        m
        for m in manager.drain_update_messages()
        if m.header.type is MsgType.REQUEST
    ]
    assert len(sent) == 1
    return manager, data_model, started, sent[0]


def assert_remote_error_answer(
    answer: object, started: FrostMessage
) -> FrostMessage:
    assert isinstance(answer, FrostMessage)
    assert answer.header.type is MsgType.ERROR
    assert answer.correlation_id == started.correlation_id
    assert isinstance(answer.payload, ErrorPayload)
    assert answer.payload.error_code is ErrorCode.UNKNOWN
    # Only the generic text goes on: the remote text is remote-controlled.
    assert answer.payload.error_message == ErrorMessages.REMOTE_ERROR.value
    assert SECRET not in answer.payload.error_message
    return answer


class TestRouting:
    def test_top_level_remote_call_error_ends_the_request(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        m = composite("m", [remote_call()])
        manager, data_model, started, request = start(m, root="m")

        with caplog.at_level(logging.ERROR):
            answer = manager.handle_message(remote_error(request))

        assert_remote_error_answer(answer, started)
        # The detail stays in the log with the request correlation id.
        assert SECRET in caplog.text
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(m)

    def test_nested_child_error_fails_the_parent_and_the_request(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, started, request = start(
            child, parent, root="parent"
        )
        assert request.correlation_id in data_model._contexts

        answer = manager.handle_message(remote_error(request))

        assert_remote_error_answer(answer, started)
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(parent, child)
        assert manager.drain_update_messages() == []

    def test_chain_answers_exactly_once(self) -> None:
        c = composite("c", [remote_call()])
        b = composite("b", [call("c")])
        a = composite("a", [call("b")])
        manager, data_model, started, request = start(c, b, a, root="a")

        answer = manager.handle_message(remote_error(request))

        assert_remote_error_answer(answer, started)
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(a, b, c)

    def test_error_code_is_remote_error_in_the_context(self) -> None:
        child = composite("child", [remote_call()])
        parent = composite("parent", [call("child")])
        manager, data_model, started, request = start(
            child, parent, root="parent"
        )
        (root_id,) = manager._running_methods
        root = parent._get_context(root_id)

        owner_result = child.handle_error(
            str(request.correlation_id), remote_error(request)
        )

        assert owner_result is not None
        assert owner_result.error is not None
        assert owner_result.error.code is ExecutionErrorCode.REMOTE_ERROR
        assert owner_result.error.node == "remote_method"
        assert root.error is not None
        assert root.error.code is ExecutionErrorCode.REMOTE_ERROR
        assert root.error.message.startswith(f"{child.qualified_name}: ")

    def test_rejected_event_subscription_fails_without_unsubscribe(
        self,
    ) -> None:
        wait = WaitRemoteEventNode(
            variable_node="remote/var",
            remote_id="remote_dm",
            rhs=1,
            op=WaitConditionOperator.EQ,
        )
        m = composite("m", [wait])
        manager, data_model, started, request = start(m, root="m")
        assert request.header.msg_name is VariableMsgName.SUBSCRIBE

        answer = manager.handle_message(remote_error(request))

        assert_remote_error_answer(answer, started)
        # The remote refused the subscription: nothing to unsubscribe.
        assert manager.drain_update_messages() == []


class TestIgnored:
    def setup_method(self) -> None:
        self.child = composite("child", [remote_call()])
        self.parent = composite("parent", [call("child")])
        (
            self.manager,
            self.data_model,
            self.started,
            self.request,
        ) = start(self.child, self.parent, root="parent")

    def assert_untouched(self) -> None:
        assert len(self.manager._running_methods) == 1
        assert len(self.data_model._contexts) == 2
        assert self.manager.drain_update_messages() == []

    def test_unknown_correlation_id(self) -> None:
        error = FrostMessageBuilder(sender="remote_dm").build_error_message(
            message=frost_request("remote_dm", "x"),
            error_code=ErrorCode.NOT_ALLOWED,
            error_message="nope",
        )

        assert self.manager.handle_message(error) is None

        self.assert_untouched()

    def test_wrong_sender(self) -> None:
        assert (
            self.manager.handle_message(
                remote_error(self.request, sender="intruder")
            )
            is None
        )

        self.assert_untouched()

    def test_wrong_target(self) -> None:
        error = replace(remote_error(self.request), target="somebody_else")

        assert self.manager.handle_message(error) is None

        self.assert_untouched()

    def test_error_header_with_a_non_error_payload(self) -> None:
        message = FrostMessage(
            sender="remote_dm",
            target="dm",
            identifier="x",
            correlation_id=self.request.correlation_id,
            header=FrostHeader(
                type=MsgType.ERROR,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node="remote_method"),
        )

        assert self.manager.handle_message(message) is None

        self.assert_untouched()

    def test_context_not_waiting_on_a_remote_node(self) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        waiting = composite("waiting", [wait_for_nonzero(trigger)])
        manager, data_model = frost_setup(waiting, variables=(trigger,))
        started = manager.handle_request(frost_request("dm", "waiting"))
        assert isinstance(started, FrostMessage)
        manager.drain_update_messages()
        (root_id,) = manager._running_methods
        error = FrostMessageBuilder(sender="remote_dm").build_error_message(
            message=FrostMessage(
                sender="dm",
                target="remote_dm",
                identifier="x",
                correlation_id=root_id,
                header=FrostHeader(
                    type=MsgType.REQUEST,
                    namespace=MsgNamespace.METHOD,
                    msg_name=MethodMsgName.INVOKE,
                ),
                payload=MethodPayload(node="remote_method"),
            ),
            error_code=ErrorCode.NOT_ALLOWED,
            error_message="nope",
        )

        assert manager.handle_message(error) is None

        assert len(manager._running_methods) == 1

    def test_duplicate_error_is_a_no_op(self) -> None:
        first = self.manager.handle_message(remote_error(self.request))
        assert isinstance(first, FrostMessage)

        assert self.manager.handle_message(remote_error(self.request)) is None

        assert self.manager._running_methods == {}
        assert self.data_model._contexts == {}

    def test_late_response_after_the_error_is_ignored(self) -> None:
        self.manager.handle_message(remote_error(self.request))
        response = FrostMessageBuilder(
            sender="remote_dm"
        ).build_method_completed_message(
            target="dm",
            correlation_id=str(self.request.correlation_id),
            ret={},
            node="remote_method",
        )

        assert self.manager.handle_message(response) is None


def test_long_remote_text_is_truncated() -> None:
    node = remote_call()
    node.set_message_builder(FrostMessageBuilder(sender="dm"))
    context = new_context()
    request = node.execute(context).messages[0]

    error = node.handle_error(context, remote_error(request, text="x" * 5000))

    assert error is not None
    assert len(error.message) < 400
    assert error.message.endswith("...")


class TestRemoteTextSanitized:
    """The remote text and code are cleaned where they enter the error."""

    def run(
        self,
        text: str = SECRET,
        code: object = None,
        remote_id: str = "remote_dm",
    ) -> ExecutionError | None:
        node = CallRemoteMethodNode(
            method_node="remote_method",
            remote_id=remote_id,
            args=[],
            kwargs={},
        )
        node.set_message_builder(FrostMessageBuilder(sender="dm"))
        context = new_context()
        request = node.execute(context).messages[0]
        answer = remote_error(request, sender=remote_id, text=text)
        if code is not None:
            assert isinstance(answer.payload, ErrorPayload)
            answer.payload.error_code = code  # type: ignore[assignment]
        return node.handle_error(context, answer)

    def test_control_characters_are_removed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        text = "line1\nline2\r\x1b[31mred\x1b[0m\x00end"
        with caplog.at_level(logging.DEBUG):
            error = self.run(text=text)

        assert error is not None
        for char in ("\n", "\r", "\x1b", "\x00"):
            assert char not in error.message
        assert "line1 line2" in error.message
        for record in caplog.records:
            rendered = record.getMessage()
            for char in ("\n", "\r", "\x1b"):
                assert char not in rendered

    def test_known_code_is_formatted_as_name(self) -> None:
        error = self.run()

        assert error is not None
        assert "NOT_ALLOWED" in error.message
        assert "ErrorCode." not in error.message
        assert "<" not in error.message

    def test_unknown_integer_code_is_formatted_as_number(self) -> None:
        error = self.run(code=987654)

        assert error is not None
        assert "error 987654:" in error.message

    def test_non_integer_code_is_bounded_and_clean(self) -> None:
        error = self.run(code="bad\ncode" + "z" * 500)

        assert error is not None
        assert "\n" not in error.message
        assert len(error.message) < 400

    def test_long_text_is_cut(self) -> None:
        error = self.run(text="y" * 5000)

        assert error is not None
        assert error.message.endswith("...")
        assert len(error.message) < 400

    def test_remote_id_is_sanitized(self) -> None:
        error = self.run(remote_id="remote\ndm\x1b[1m" + "r" * 200)

        assert error is not None
        assert "\n" not in error.message
        assert "\x1b" not in error.message
        assert len(error.message) < 400


class TestFinishOwnership:
    """`_finish_if_terminated` claims the request before answering it."""

    def test_running_request_stays_registered(self) -> None:
        m = composite("m", [remote_call()])
        manager, _, _, _ = start(m, root="m")
        (root_id,) = manager._running_methods
        before = manager._running_methods[root_id]

        assert manager._finish_if_terminated(root_id) is None

        assert manager._running_methods[root_id] is before

    def test_reentrant_finish_does_not_answer_twice(self) -> None:
        m = composite("m", [remote_call()])
        manager, data_model, started, request = start(m, root="m")
        (root_id,) = manager._running_methods
        m._contexts[root_id].fail(
            ExecutionError(ExecutionErrorCode.TIMEOUT, "late")
        )
        nested: list[FrostMessage | None] = []
        real_delete = m.delete_context

        def delete_and_retrigger(context_id: str) -> None:
            # A second trigger arrives while the first is still answering.
            nested.append(manager._finish_if_terminated(root_id))
            real_delete(context_id)

        m.delete_context = delete_and_retrigger  # type: ignore[method-assign]

        answer = manager._finish_if_terminated(root_id)

        assert isinstance(answer, FrostMessage)
        assert answer.correlation_id == started.correlation_id
        assert nested == [None]
        assert manager._running_methods == {}
        assert data_model._contexts == {}

    def test_no_lost_wakeup_when_the_request_ends_during_the_check(
        self,
    ) -> None:
        m = composite("m", [remote_call()])
        manager, data_model, started, _ = start(m, root="m")
        (root_id,) = manager._running_methods
        context = m._contexts[root_id]
        answers: list[FrostMessage | None] = []
        real_is_terminated = m.is_terminated
        calls = 0

        def is_terminated(context_id: str) -> bool:
            nonlocal calls
            calls += 1
            if calls > 1:
                return real_is_terminated(context_id)
            # Still running when A looks; then another trigger ends it and
            # answers before A goes on.
            running = real_is_terminated(context_id)
            context.fail(ExecutionError(ExecutionErrorCode.TIMEOUT, "late"))
            answers.append(manager._finish_if_terminated(root_id))
            return running

        m.is_terminated = is_terminated  # type: ignore[method-assign]

        first = manager._finish_if_terminated(root_id)

        assert first is None
        (second,) = answers
        assert isinstance(second, FrostMessage)
        assert second.correlation_id == started.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}

    def test_exception_while_answering_keeps_the_request(self) -> None:
        m = composite("m", [remote_call()])
        manager, data_model, started, _ = start(m, root="m")
        (root_id,) = manager._running_methods
        m._contexts[root_id].fail(
            ExecutionError(ExecutionErrorCode.TIMEOUT, "late")
        )
        real = m.get_completed_return_values
        failures = [True]

        def flaky(context_id: str) -> dict[str, object] | None:
            if failures:
                failures.pop()
                raise RuntimeError("boom")
            return real(context_id)

        m.get_completed_return_values = flaky  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="boom"):
            manager._finish_if_terminated(root_id)

        assert root_id in manager._running_methods
        answer = manager._finish_if_terminated(root_id)
        assert isinstance(answer, FrostMessage)
        assert answer.correlation_id == started.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}

    def test_non_error_payload_is_logged_at_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        m = composite("m", [remote_call()])
        manager, _, _, request = start(m, root="m")
        message = FrostMessageBuilder(
            sender="remote_dm"
        ).build_method_completed_message(
            target="dm",
            correlation_id=str(request.correlation_id),
            ret={},
            node="remote_method",
        )
        message.header.type = MsgType.ERROR

        with caplog.at_level(logging.DEBUG):
            assert manager.handle_error(message) is None

        levels = {r.levelno for r in caplog.records}
        assert logging.WARNING not in levels
        assert "without error payload" in caplog.text


def remote_nodes() -> list[tuple[str, RemoteExecutionNode, tuple[object, ...]]]:
    return [
        (
            "call",
            CallRemoteMethodNode(
                method_node="remote_method",
                remote_id="remote_dm",
                args=[],
                kwargs={},
            ),
            (MsgNamespace.METHOD, MethodMsgName.INVOKE),
        ),
        (
            "read",
            ReadRemoteVariableNode(
                variable_node="remote/var",
                remote_id="remote_dm",
                store_as="x",
            ),
            (MsgNamespace.VARIABLE, VariableMsgName.READ),
        ),
        (
            "write",
            WriteRemoteVariableNode(
                variable_node="remote/var", remote_id="remote_dm", value=1
            ),
            (MsgNamespace.VARIABLE, VariableMsgName.WRITE),
        ),
        (
            "wait",
            WaitRemoteEventNode(
                variable_node="remote/var",
                remote_id="remote_dm",
                rhs=1,
                op=WaitConditionOperator.EQ,
            ),
            (MsgNamespace.VARIABLE, VariableMsgName.SUBSCRIBE),
        ),
    ]


@pytest.mark.parametrize("index", range(4))
class TestRequestKind:
    """An error only answers the kind of request the node sent."""

    def prepare(
        self, index: int
    ) -> tuple[RemoteExecutionNode, tuple[object, ...], FrostMessage, object]:
        _, node, kind = remote_nodes()[index]
        node.set_message_builder(FrostMessageBuilder(sender="dm"))
        context = new_context()
        request = node.execute(context).messages[0]
        return node, kind, request, context

    def with_header(
        self, request: FrostMessage, namespace: MsgNamespace, name: MsgName
    ) -> FrostMessage:
        error = remote_error(request)
        return replace(
            error,
            header=FrostHeader(
                type=MsgType.ERROR, namespace=namespace, msg_name=name
            ),
        )

    def test_the_matching_error_is_accepted(self, index: int) -> None:
        node, kind, request, context = self.prepare(index)

        error = node.handle_error(context, remote_error(request))  # type: ignore[arg-type]

        assert error is not None
        assert error.code is ExecutionErrorCode.REMOTE_ERROR

    def test_wrong_namespace_is_ignored(self, index: int) -> None:
        node, kind, request, context = self.prepare(index)
        other = (
            MsgNamespace.NODE
            if kind[0] is not MsgNamespace.NODE
            else MsgNamespace.METHOD
        )

        message = self.with_header(request, other, kind[1])  # type: ignore[arg-type]

        assert node.handle_error(context, message) is None  # type: ignore[arg-type]

    def test_wrong_msg_name_is_ignored(self, index: int) -> None:
        node, kind, request, context = self.prepare(index)
        wrong = (
            VariableMsgName.UNSUBSCRIBE
            if kind[0] is MsgNamespace.VARIABLE
            else MethodMsgName.COMPLETED
        )

        message = self.with_header(request, kind[0], wrong)  # type: ignore[arg-type]

        assert node.handle_error(context, message) is None  # type: ignore[arg-type]

    def test_error_of_another_kind_of_the_same_namespace_is_ignored(
        self, index: int
    ) -> None:
        node, kind, request, context = self.prepare(index)
        names: list[MsgName] = (
            [
                VariableMsgName.READ,
                VariableMsgName.WRITE,
                VariableMsgName.SUBSCRIBE,
            ]
            if kind[0] is MsgNamespace.VARIABLE
            else [MethodMsgName.STARTED, MethodMsgName.COMPLETED]
        )

        for name in names:
            if name is kind[1]:
                continue
            message = self.with_header(request, kind[0], name)  # type: ignore[arg-type]
            assert node.handle_error(context, message) is None  # type: ignore[arg-type]


def test_a_node_without_a_declared_kind_never_accepts_an_error() -> None:
    class Undeclared(CallRemoteMethodNode):
        request_kind = None  # type: ignore[assignment]

    node = Undeclared(
        method_node="remote_method", remote_id="remote_dm", args=[], kwargs={}
    )
    node.set_message_builder(FrostMessageBuilder(sender="dm"))
    context = new_context()
    request = node.execute(context).messages[0]

    assert node.handle_error(context, remote_error(request)) is None


def test_every_remote_node_declares_its_request_kind() -> None:
    kinds = {name: node.request_kind for name, node, _ in remote_nodes()}

    assert kinds == {
        "call": (MsgNamespace.METHOD, MethodMsgName.INVOKE),
        "read": (MsgNamespace.VARIABLE, VariableMsgName.READ),
        "write": (MsgNamespace.VARIABLE, VariableMsgName.WRITE),
        "wait": (MsgNamespace.VARIABLE, VariableMsgName.SUBSCRIBE),
    }
