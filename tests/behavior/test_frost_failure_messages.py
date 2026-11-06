"""Messages produced before a failure must leave under Frost."""

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    execution_error,
    execution_success,
)
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.local_execution_node import LocalExecutionNode
from machine_data_model.behavior.remote_execution_node import (
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
from tests.behavior import (
    ERROR,
    assert_no_contexts,
    failing_stub,
    frost_request,
    frost_setup,
)


def marker(text: str) -> FrostMessage:
    return FrostMessageBuilder(sender="dm").build_unsubscribe_variable_message(
        target="remote_dm", node=text
    )


class Sending(LocalExecutionNode):
    """Node that returns messages with a success or an error."""

    def __init__(self, messages: list[FrostMessage], fail: bool) -> None:
        super().__init__(node="")
        self._messages = messages
        self._fail = fail

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        if self._fail:
            return execution_error(ERROR, list(self._messages))
        return execution_success(list(self._messages))


class FlakyWait(WaitRemoteEventNode):
    """Remote event wait that raises when it runs after its response."""

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        if context.has_value("__started__") and context.active_request is None:
            raise RuntimeError("flaky")
        context.set_value("__started__", True)
        return super().execute(context)


def remote_wait(
    cls: type[WaitRemoteEventNode] = WaitRemoteEventNode,
) -> WaitRemoteEventNode:
    return cls(
        variable_node="remote/var",
        remote_id="remote_dm",
        rhs=1,
        op=WaitConditionOperator.EQ,
    )


def composite(name: str, nodes: list[ControlFlowNode]) -> CompositeMethodNode:
    return CompositeMethodNode(
        id=name, name=name, cfg=ControlFlow(nodes=list(nodes), strict=False)
    )


def unsubscribes(messages: list[FrostMessage]) -> list[FrostMessage]:
    return [
        m
        for m in messages
        if m.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.UNSUBSCRIBE,
        )
    ]


class TestSyncOutcomes:
    def test_sync_failure_forwards_the_messages(self) -> None:
        note = marker("note")
        m = composite("m", [Sending([note], fail=True)])
        manager, data_model = frost_setup(m)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.ERROR
        assert manager.drain_update_messages() == [note]
        assert_no_contexts(m)

    def test_sync_completion_forwards_the_messages(self) -> None:
        note = marker("note")
        m = composite("m", [Sending([note], fail=False)])
        manager, data_model = frost_setup(m)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.RESPONSE
        assert manager.drain_update_messages() == [note]

    def test_running_request_still_forwards_its_messages(self) -> None:
        m = composite("m", [remote_wait()])
        manager, data_model = frost_setup(m)

        started = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(started, FrostMessage)
        sent = manager.drain_update_messages()
        assert [x.header.msg_name for x in sent] == [VariableMsgName.SUBSCRIBE]


class TestAfterResume:
    def event(self, request: FrostMessage) -> FrostMessage:
        return FrostMessageBuilder(
            sender="remote_dm"
        ).build_variable_update_message(
            target=request.sender,
            correlation_id=request.correlation_id,
            node="remote/var",
            value=1,
        )

    def test_failure_after_resume_forwards_the_cleanup(self) -> None:
        m = composite("m", [remote_wait(), failing_stub()])
        manager, data_model = frost_setup(m)
        started = manager.handle_request(frost_request("dm", "m"))
        assert isinstance(started, FrostMessage)
        (request,) = manager.drain_update_messages()

        answer = manager.handle_message(self.event(request))

        # The cleanup of the satisfied wait (unsubscribe) left, and so did
        # the error answer.
        assert isinstance(answer, FrostMessage)
        assert answer.header.type is MsgType.ERROR
        assert answer.correlation_id == started.correlation_id
        assert len(unsubscribes(manager.drain_update_messages())) == 1
        assert manager._running_methods == {}
        assert data_model._contexts == {}
        assert_no_contexts(m)

    def test_release_unsubscribe_leaves_with_the_failure(self) -> None:
        m = composite("m", [remote_wait(FlakyWait)])
        manager, data_model = frost_setup(m)
        started = manager.handle_request(frost_request("dm", "m"))
        assert isinstance(started, FrostMessage)
        (request,) = manager.drain_update_messages()

        answer = manager.handle_message(self.event(request))

        assert isinstance(answer, FrostMessage)
        assert answer.header.type is MsgType.ERROR
        sent = unsubscribes(manager.drain_update_messages())
        assert len(sent) == 1
        assert sent[0].correlation_id == request.correlation_id
        assert manager._running_methods == {}
        assert data_model._contexts == {}
