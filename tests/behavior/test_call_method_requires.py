"""A call node whose callee rejects the call because of its `requires`."""

import logging
from typing import Any

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import execution_success
from machine_data_model.behavior.execution_error import ExecutionErrorCode
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
    ErrorPayload,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)
from tests.behavior import StubNode, assert_no_contexts, frost_request

EQ = WaitConditionOperator.EQ


class Setup:
    """A parent composite that calls a callee guarded by `requires`."""

    def __init__(self, composite_callee: bool, mode: float = 1) -> None:
        self.calls: list[dict[str, Any]] = []
        self.callee_stub = StubNode(lambda: execution_success())
        self.after = StubNode(lambda: execution_success())
        self.mode = NumericalVariableNode(id="mode", name="mode", value=mode)
        requires = [Condition("mode", EQ, 2)]
        self.callee: MethodNode
        if composite_callee:
            self.callee = CompositeMethodNode(
                id="callee",
                name="callee",
                cfg=ControlFlow(nodes=[self.callee_stub]),
                requires=requires,
            )
        else:
            self.callee = MethodNode(
                id="callee",
                name="callee",
                returns=[NumericalVariableNode(id="r", name="r", value=0)],
                callback=self.record,
                requires=requires,
            )
        call = CallMethodNode(method_node="callee", args=[], kwargs={})
        call.set_ref_node(self.callee)
        self.parent = CompositeMethodNode(
            id="parent",
            name="parent",
            cfg=ControlFlow(nodes=[call, self.after]),
        )
        self.data_model = DataModel(name="dm")
        for node in (self.mode, self.callee, self.parent):
            self.data_model.root.add_child(node)
        self.data_model._register_nodes(self.data_model.root)

    def record(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        return 0

    def callee_ran(self) -> bool:
        return bool(self.calls) or self.callee_stub.runs > 0


kinds = pytest.mark.parametrize("composite_callee", [False, True])


@kinds
class TestCallRejected:
    def test_the_call_fails_with_the_precondition_error(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee)

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert result.error.node == setup.callee.qualified_name
        assert result.error.origin == setup.callee.qualified_name
        message = result.error.message
        assert message.startswith(f"{setup.callee.qualified_name}: ")
        assert "mode == 2 not met" in message
        assert not setup.callee_ran()
        assert setup.after.runs == 0

    def test_observed_value_is_carried(self, composite_callee: bool) -> None:
        setup = Setup(composite_callee, mode=7)

        result = setup.parent()

        assert result.error is not None
        assert result.error.observed == "mode = 7"
        assert "7" not in result.error.message.replace("mode == 2", "")

    def test_it_is_not_an_unexpected_error(
        self, composite_callee: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        setup = Setup(composite_callee)

        with caplog.at_level(logging.DEBUG):
            result = setup.parent()

        assert result.error is not None
        assert result.error.code is not ExecutionErrorCode.UNEXPECTED_ERROR
        assert not [r for r in caplog.records if r.exc_info]
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_it_does_not_raise_in_strict_mode(
        self, composite_callee: bool
    ) -> None:
        # The test configuration runs the control flow in strict mode, where
        # an unexpected exception is re-raised: this one must not be.
        setup = Setup(composite_callee)
        assert setup.parent.cfg.strict is True

        assert setup.parent().error is not None

    def test_it_is_the_same_outside_strict_mode(
        self, composite_callee: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setup = Setup(composite_callee)
        monkeypatch.setattr(ControlFlow, "default_strict", False)

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET

    def test_no_context_is_left_behind(self, composite_callee: bool) -> None:
        setup = Setup(composite_callee)

        setup.parent()

        assert_no_contexts(setup.parent)
        if isinstance(setup.callee, CompositeMethodNode):
            assert_no_contexts(setup.callee)
        assert setup.data_model._contexts == {}

    def test_the_call_goes_through_when_the_condition_holds(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, mode=2)

        result = setup.parent()

        assert result.error is None
        assert setup.callee_ran()
        assert setup.after.runs == 1


class TestCodes:
    def test_no_data_code_is_kept(self) -> None:
        setup = Setup(composite_callee=False)
        setup.mode._update_internal_value(None)  # type: ignore[arg-type]

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.NO_DATA

    def test_invalid_configuration_code_is_kept(self) -> None:
        setup = Setup(composite_callee=False)
        setup.callee._requires = (Condition("nope", EQ, 1),)

        result = setup.parent()

        assert result.error is not None
        assert result.error.code is ExecutionErrorCode.INVALID_CONFIGURATION


@kinds
class TestOverFrost:
    def test_invoking_the_parent_answers_not_allowed(
        self, composite_callee: bool
    ) -> None:
        setup = Setup(composite_callee, mode=987654)
        manager = FrostProtocolMng(setup.data_model)

        response = manager.handle_request(frost_request("dm", "parent"))

        assert isinstance(response, FrostMessage)
        assert response.header.type is MsgType.ERROR
        assert isinstance(response.payload, ErrorPayload)
        assert response.payload.error_code is ErrorCode.NOT_ALLOWED
        assert "mode == 2 not met" in str(response.payload.error_message)
        assert "987654" not in str(response.payload.error_message)
        assert manager._running_methods == {}
        assert not setup.callee_ran()
