"""A Frost INVOKE of a method whose `requires` do not hold is answered."""

import logging
from typing import Any
import uuid

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import execution_success
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)
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
from tests.behavior import StubNode

EQ = WaitConditionOperator.EQ


def cond(variable: str, rhs: Any) -> Condition:
    return Condition(variable, EQ, rhs)


def invoke(node: str, **kwargs: Any) -> FrostMessage:
    return FrostMessage(
        sender="client",
        target="dm",
        identifier=str(uuid.uuid4()),
        header=FrostHeader(
            type=MsgType.REQUEST,
            namespace=MsgNamespace.METHOD,
            msg_name=MethodMsgName.INVOKE,
        ),
        payload=MethodPayload(node=node, kwargs=kwargs),
    )


class Setup:
    def __init__(
        self,
        requires: list[Condition],
        composite: bool,
        mode: float = 1,
        parameters: list[Any] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.stub = StubNode(lambda: execution_success())
        self.mode = NumericalVariableNode(id="mode", name="mode", value=mode)
        self.method: MethodNode
        if composite:
            self.method = CompositeMethodNode(
                id="m",
                name="m",
                parameters=parameters,
                cfg=ControlFlow(nodes=[self.stub]),
                requires=requires,
            )
        else:
            self.method = MethodNode(
                id="m",
                name="m",
                parameters=parameters,
                returns=[NumericalVariableNode(id="r", name="r", value=0)],
                callback=self.record,
                requires=requires,
            )
        self.data_model = DataModel(name="dm")
        self.data_model.root.add_child(self.mode)
        self.data_model.root.add_child(self.method)
        self.data_model._register_nodes(self.data_model.root)
        self.manager = FrostProtocolMng(self.data_model)

    def record(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        return 0

    def ran(self) -> bool:
        return bool(self.calls) or self.stub.runs > 0

    def answer(self, **kwargs: Any) -> FrostMessage:
        response = self.manager.handle_request(invoke("m", **kwargs))
        assert isinstance(response, FrostMessage)
        return response


def error_of(response: FrostMessage) -> ErrorPayload:
    assert response.header.type is MsgType.ERROR
    assert isinstance(response.payload, ErrorPayload)
    return response.payload


kinds = pytest.mark.parametrize("composite", [False, True])


@kinds
class TestRejections:
    def test_unmet_precondition_is_not_allowed(self, composite: bool) -> None:
        setup = Setup([cond("mode", 2)], composite)

        payload = error_of(setup.answer())

        assert payload.error_code is ErrorCode.NOT_ALLOWED
        text = str(payload.error_message)
        assert text.startswith(f"{ErrorMessages.PRECONDITION_NOT_MET.value}: ")
        assert "mode == 2 not met" in text
        assert not setup.ran()

    def test_no_data_is_not_allowed_with_its_own_text(
        self, composite: bool
    ) -> None:
        setup = Setup([cond("mode", 1)], composite)
        setup.mode._update_internal_value(None)  # type: ignore[arg-type]

        payload = error_of(setup.answer())

        assert payload.error_code is ErrorCode.NOT_ALLOWED
        assert str(payload.error_message).startswith(
            f"{ErrorMessages.NO_DATA.value}: "
        )
        assert not setup.ran()

    def test_invalid_configuration_is_bad_request(
        self, composite: bool
    ) -> None:
        setup = Setup([cond("nope", 1)], composite)

        payload = error_of(setup.answer())

        assert payload.error_code is ErrorCode.BAD_REQUEST
        assert str(payload.error_message).startswith(
            f"{ErrorMessages.BAD_REQUEST.value}: "
        )
        assert not setup.ran()

    def test_observed_value_is_not_sent(self, composite: bool) -> None:
        setup = Setup([cond("mode", 2)], composite, mode=987654)

        response = setup.answer()

        assert "987654" not in str(error_of(response).error_message)
        assert "987654" not in repr(response)

    def test_answer_correlates_with_the_request(self, composite: bool) -> None:
        setup = Setup([cond("mode", 2)], composite)
        request = invoke("m")

        response = setup.manager.handle_request(request)

        assert isinstance(response, FrostMessage)
        assert response.correlation_id == request.correlation_id
        assert response.target == "client"

    def test_rejection_registers_nothing(self, composite: bool) -> None:
        setup = Setup([cond("mode", 2)], composite)

        setup.answer()

        assert setup.manager._running_methods == {}
        assert setup.data_model._contexts == {}
        assert setup.manager.drain_update_messages() == []
        if isinstance(setup.method, CompositeMethodNode):
            assert setup.method._contexts == {}

    def test_rejection_is_logged_without_a_traceback(
        self, composite: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        setup = Setup([cond("mode", 2)], composite)

        with caplog.at_level(logging.DEBUG):
            setup.answer()

        assert not [r for r in caplog.records if r.exc_info]
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert "not satisfied" in caplog.text

    def test_parameters_from_the_request_feed_the_conditions(
        self, composite: bool
    ) -> None:
        params = [NumericalVariableNode(id="want", name="want", value=1)]
        setup = Setup([cond("mode", "${want}")], composite, parameters=params)

        rejected = setup.answer(want=2)
        accepted = setup.answer(want=1)

        assert error_of(rejected).error_code is ErrorCode.NOT_ALLOWED
        assert accepted.header.type is not MsgType.ERROR
        assert setup.ran()


@kinds
class TestSuccessUnchanged:
    def test_holding_requires_let_the_method_run(self, composite: bool) -> None:
        setup = Setup([cond("mode", 1)], composite)

        response = setup.answer()

        assert response.header.type is not MsgType.ERROR
        assert setup.ran()

    def test_method_without_requires_is_unchanged(
        self, composite: bool
    ) -> None:
        setup = Setup([], composite)

        response = setup.answer()

        assert response.header.type is not MsgType.ERROR
        assert setup.ran()

    def test_same_method_is_accepted_once_the_condition_holds(
        self, composite: bool
    ) -> None:
        setup = Setup([cond("mode", 2)], composite)
        assert error_of(setup.answer()).error_code is ErrorCode.NOT_ALLOWED

        setup.mode.write(2)
        response = setup.answer()

        assert response.header.type is not MsgType.ERROR
        assert setup.ran()


def test_string_parameter_template_in_variable_path() -> None:
    params = [StringVariableNode(id="which", name="which", value="mode")]
    setup = Setup([cond("${which}", 2)], composite=False, parameters=params)

    rejected = setup.answer(which="mode")

    assert error_of(rejected).error_code is ErrorCode.NOT_ALLOWED
    assert not setup.ran()
