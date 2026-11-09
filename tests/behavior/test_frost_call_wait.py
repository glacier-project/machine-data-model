"""`on_unmet: wait` through a real `FrostProtocolMng`, end to end."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from machine_data_model.behavior import local_execution_node
from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    execution_success,
)
from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import MsgType
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
from tests.behavior import StubNode, frost_request

EQ = WaitConditionOperator.EQ


def waiting_call(
    callee: str, on_unmet: str = "wait", **kwargs: Any
) -> CallMethodNode:
    return CallMethodNode(
        method_node=callee, args=[], kwargs={}, on_unmet=on_unmet, **kwargs
    )


class Model:
    """A callee guarded by `mode == 2`, reached through a chain of callers.

    `depth` is the number of composite callers: 1 is `parent -> callee`,
    2 is `a -> b -> callee` (the wait is in `b`).
    """

    def __init__(
        self,
        composite_callee: bool = False,
        depth: int = 1,
        timeout: float | None = None,
        mode: float = 1,
        requires: list[Condition] | None = None,
        on_unmet: str = "wait",
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.callee_stub = StubNode(lambda: execution_success())
        self.mode = NumericalVariableNode(id="mode", name="mode", value=mode)
        self.level = NumericalVariableNode(id="level", name="level", value=0)
        conditions = requires or [Condition("mode", EQ, 2)]
        self.callee: MethodNode
        if composite_callee:
            self.callee = CompositeMethodNode(
                id="callee",
                name="callee",
                cfg=ControlFlow(nodes=[self.callee_stub]),
                requires=conditions,
            )
        else:
            self.callee = MethodNode(
                id="callee",
                name="callee",
                returns=[NumericalVariableNode(id="r", name="r", value=0)],
                callback=self.record,
                requires=conditions,
            )
        self.callers: list[CompositeMethodNode] = []
        inner = self.make_caller(
            "c0", waiting_call("callee", on_unmet, timeout=timeout)
        )
        self.callers.append(inner)
        for level in range(1, depth):
            outer_call = CallMethodNode(
                method_node=self.callers[-1].id,
                args=[],
                kwargs={},
                on_unmet="fail",
            )
            self.callers.append(self.make_caller(f"c{level}", outer_call))
        self.root = self.callers[-1]
        self.data_model = DataModel(name="dm")
        for node in (self.mode, self.level, self.callee, *self.callers):
            self.data_model.root.add_child(node)
        self.data_model._register_nodes(self.data_model.root)
        self.manager = FrostProtocolMng(self.data_model)

    def make_caller(
        self, name: str, call: ControlFlowNode
    ) -> CompositeMethodNode:
        return CompositeMethodNode(
            id=name, name=name, cfg=ControlFlow(nodes=[call])
        )

    def record(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        return 0

    def callee_runs(self) -> int:
        return len(self.calls) + self.callee_stub.runs

    def invoke(self) -> FrostMessage:
        response = self.manager.handle_request(
            frost_request("dm", self.root.id)
        )
        assert isinstance(response, FrostMessage)
        self.manager.clear_update_messages()
        return response

    def assert_clean(self) -> None:
        assert self.manager._running_methods == {}
        assert self.data_model._contexts == {}
        for caller in self.callers:
            assert caller._contexts == {}
            assert caller._completed_results == {}
        assert self.mode.get_subscriptions() == []
        assert self.level.get_subscriptions() == []


kinds = pytest.mark.parametrize("composite_callee", [False, True])
depths = pytest.mark.parametrize("depth", [1, 2])


@kinds
@depths
class TestWaitCompletes:
    def test_started_then_one_response_after_the_write(
        self, composite_callee: bool, depth: int
    ) -> None:
        model = Model(composite_callee, depth)

        started = model.invoke()

        assert started.header.type is not MsgType.ERROR
        assert model.callee_runs() == 0
        assert len(model.manager._running_methods) == 1

        model.mode.write(2)

        updates = model.manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].header.type is MsgType.RESPONSE
        assert isinstance(updates[0].payload, MethodPayload)
        assert updates[0].correlation_id == started.correlation_id
        assert model.callee_runs() == 1
        model.assert_clean()

    def test_a_change_that_does_not_satisfy_sends_nothing(
        self, composite_callee: bool, depth: int
    ) -> None:
        model = Model(composite_callee, depth)
        model.invoke()

        model.mode.write(3)

        assert model.manager.drain_update_messages() == []
        assert model.callee_runs() == 0
        assert len(model.manager._running_methods) == 1
        # Still waiting: subscribed again after the retry.
        assert len(model.mode.get_subscriptions()) == 1

        model.mode.write(2)

        assert len(model.manager.drain_update_messages()) == 1
        assert model.callee_runs() == 1
        model.assert_clean()

    def test_two_requests_are_answered_independently(
        self, composite_callee: bool, depth: int
    ) -> None:
        model = Model(composite_callee, depth)
        first = model.invoke()
        second = model.invoke()
        assert len(model.manager._running_methods) == 2

        model.mode.write(2)

        updates = model.manager.drain_update_messages()
        assert sorted(str(u.correlation_id) for u in updates) == sorted(
            [str(first.correlation_id), str(second.correlation_id)]
        )
        assert model.callee_runs() == 2
        model.assert_clean()

    def test_a_duplicate_write_is_a_no_op(
        self, composite_callee: bool, depth: int
    ) -> None:
        model = Model(composite_callee, depth)
        model.invoke()

        model.mode.write(2)
        model.mode.write(2)

        assert len(model.manager.drain_update_messages()) == 1
        assert model.callee_runs() == 1


class TestRequiresHoldAtOnce:
    @kinds
    def test_no_wait_and_a_normal_response(
        self, composite_callee: bool
    ) -> None:
        model = Model(composite_callee, mode=2)

        response = model.manager.handle_request(
            frost_request("dm", model.root.id)
        )

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.RESPONSE
        assert model.callee_runs() == 1
        model.assert_clean()


class TestWritingCallee:
    def test_a_callee_that_writes_a_watched_variable_runs_once(self) -> None:
        model = Model(requires=[Condition("mode", EQ, 2)])
        real = model.callee._callback

        def callback(**kwargs: Any) -> Any:
            # Writes the variable the wait was subscribed to.
            model.mode.write(2)
            return real(**kwargs)

        model.callee._callback = callback
        started = model.invoke()

        model.mode.write(2)

        updates = model.manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].correlation_id == started.correlation_id
        assert model.callee_runs() == 1
        model.assert_clean()


class TestTimeoutOverFrost:
    class Clock:
        now = 500.0

        def monotonic(self) -> float:
            return self.now

    @kinds
    def test_resume_after_the_deadline_answers_with_an_error(
        self, composite_callee: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = self.Clock()
        monkeypatch.setattr(local_execution_node, "time", clock)
        model = Model(composite_callee, timeout=30)
        started = model.invoke()
        (root_id,) = model.manager._running_methods

        clock.now += 31
        answer = model.manager._resume_composite_method(root_id)

        assert isinstance(answer, FrostMessage)
        assert answer.header.type is MsgType.ERROR
        assert answer.correlation_id == started.correlation_id
        assert isinstance(answer.payload, ErrorPayload)
        assert answer.payload.error_code is ErrorCode.UNKNOWN
        text = str(answer.payload.error_message)
        assert text.startswith(f"{ErrorMessages.TIMEOUT.value}: ")
        assert "timed out after 30 s" in text
        assert "mode == 2 not met" in text
        assert model.callee_runs() == 0
        model.assert_clean()


class TestRemoteValue:
    def test_waits_for_the_first_value_of_a_remote_variable(self) -> None:
        remote = NumericalVariableNode(
            id="remote", name="remote", value=2, connector_name="c"
        )
        remote.set_connector(MagicMock())
        model = Model(requires=[Condition("remote", EQ, 2)])
        model.data_model.root.add_child(remote)
        model.data_model._register_nodes(model.data_model.root)
        model.manager = FrostProtocolMng(model.data_model)
        started = model.invoke()
        # The default would satisfy the condition, but nothing was received.
        assert model.callee_runs() == 0

        remote._remote_subscription_callback(2, MagicMock())

        updates = model.manager.drain_update_messages()
        assert len(updates) == 1
        assert updates[0].correlation_id == started.correlation_id
        assert model.callee_runs() == 1
        assert remote.get_subscriptions() == []


class TestFailMode:
    def test_unmet_requires_are_answered_at_once(self) -> None:
        model = Model(on_unmet="fail")

        response = model.manager.handle_request(
            frost_request("dm", model.root.id)
        )

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.ERROR
        assert isinstance(response.payload, ErrorPayload)
        assert response.payload.error_code is ErrorCode.NOT_ALLOWED
        model.assert_clean()
