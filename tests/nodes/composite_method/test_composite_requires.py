"""`requires` of composite methods: rejection before a context exists."""

from typing import Any

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    ConditionError,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import execution_success
from machine_data_model.behavior.execution_error import ExecutionErrorCode
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodPreconditionError
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)
from tests.behavior import StubNode, assert_no_contexts

EQ = WaitConditionOperator.EQ


def cond(variable: str, rhs: Any) -> Condition:
    return Condition(variable, EQ, rhs)


class Model:
    def __init__(
        self,
        requires: list[Condition],
        mode: float = 1,
        parameters: list[Any] | None = None,
    ) -> None:
        self.stub = StubNode(lambda: execution_success())
        self.pre: list[dict[str, Any]] = []
        self.mode = NumericalVariableNode(id="mode", name="mode", value=mode)
        self.method = CompositeMethodNode(
            id="c",
            name="c",
            parameters=parameters,
            cfg=ControlFlow(nodes=[self.stub]),
            requires=requires,
        )
        self.method.pre_callback = lambda **kwargs: self.pre.append(kwargs)
        self.data_model = DataModel(name="dm")
        self.data_model.root.add_child(self.mode)
        self.data_model.root.add_child(self.method)
        self.data_model._register_nodes(self.data_model.root)


class TestCompositeRequires:
    def test_defaults_to_empty(self) -> None:
        assert CompositeMethodNode(name="c").requires == ()

    def test_rejected_before_a_context_is_created(self) -> None:
        model = Model([cond("mode", 2)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert error.node == model.method.qualified_name
        assert "mode == 2 not met" in error.message
        assert error.observed == "mode = 1"
        assert_no_contexts(model.method)
        assert model.data_model._contexts == {}

    def test_rejected_call_runs_nothing(self) -> None:
        model = Model([cond("mode", 2)])

        with pytest.raises(MethodPreconditionError):
            model.method()

        assert model.stub.runs == 0
        assert model.pre == []

    def test_repeated_rejections_leave_nothing_behind(self) -> None:
        model = Model([cond("mode", 2)])

        for _ in range(3):
            with pytest.raises(MethodPreconditionError):
                model.method()

        assert_no_contexts(model.method)
        assert model.data_model._contexts == {}

    def test_holding_requires_start_the_method(self) -> None:
        model = Model([cond("mode", 1)])

        result = model.method()

        assert result.error is None
        assert model.stub.runs == 1
        assert model.pre == [{}]

    def test_no_data_is_distinct_from_not_met(self) -> None:
        model = Model([cond("mode", 1)])
        model.mode._update_internal_value(None)  # type: ignore[arg-type]

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        assert info.value.error.code is ExecutionErrorCode.NO_DATA
        assert_no_contexts(model.method)

    def test_invalid_configuration(self) -> None:
        model = Model([cond("nope", 1)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        assert info.value.error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert model.stub.runs == 0

    def test_becomes_callable_when_the_condition_holds(self) -> None:
        model = Model([cond("mode", 2)])
        with pytest.raises(MethodPreconditionError):
            model.method()

        model.mode.write(2)
        model.method()

        assert model.stub.runs == 1


class TestCompositeParameters:
    @staticmethod
    def parameters() -> list[Any]:
        return [
            StringVariableNode(id="which", name="which", value="mode"),
            NumericalVariableNode(id="want", name="want", value=1),
        ]

    def test_parameters_feed_the_conditions(self) -> None:
        model = Model(
            [cond("${which}", "${want}")], parameters=self.parameters()
        )

        model.method(which="mode", want=1)
        with pytest.raises(MethodPreconditionError):
            model.method(which="mode", want=2)

        assert model.stub.runs == 1
        assert len(model.method._contexts) <= 1

    def test_positional_arguments_are_used(self) -> None:
        model = Model(
            [cond("${which}", "${want}")], parameters=self.parameters()
        )

        model.method("mode", 1)

        assert model.stub.runs == 1

    def test_unknown_template_is_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="not a parameter"):
            CompositeMethodNode(name="c", requires=[cond("${x}", 1)])


class TestCompositeHelpers:
    def test_evaluate_requires_does_not_start_anything(self) -> None:
        model = Model([cond("mode", 1)])

        outcomes = model.method.evaluate_requires()

        assert [o.result.value for o in outcomes] == ["ok"]
        assert model.stub.runs == 0
        assert model.pre == []
        assert_no_contexts(model.method)

    def test_evaluate_requires_propagates_configuration_errors(self) -> None:
        model = Model([cond("nope", 1)])

        with pytest.raises(ConditionError):
            model.method.evaluate_requires()

    def test_is_executable_agrees_with_the_call(self) -> None:
        model = Model([cond("mode", 2)])
        assert model.method.is_executable() is False

        model.mode.write(2)

        assert model.method.is_executable() is True
        assert model.stub.runs == 0
