"""`requires` of method nodes: rejection of a call whose conditions fail."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.execution_error import ExecutionErrorCode
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.method_node import (
    AsyncMethodNode,
    MethodNode,
    MethodPreconditionError,
)
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)

EQ = WaitConditionOperator.EQ
GT = WaitConditionOperator.GT


def cond(variable: str, op: WaitConditionOperator, rhs: Any) -> Condition:
    return Condition(variable, op, rhs)


class Model:
    """A data model with a mode variable and one method."""

    def __init__(
        self,
        requires: list[Condition],
        mode: float = 1,
        method_class: type[MethodNode] = MethodNode,
        parameters: list[Any] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.pre: list[dict[str, Any]] = []
        self.post: list[Any] = []
        self.mode = NumericalVariableNode(id="mode", name="mode", value=mode)
        self.level = NumericalVariableNode(id="level", name="level", value=5)
        self.method = method_class(
            id="m",
            name="m",
            parameters=parameters,
            returns=[NumericalVariableNode(id="r", name="r", value=0)],
            callback=self.record,
            requires=requires,
        )
        self.method.pre_callback = lambda **kwargs: self.pre.append(kwargs)
        self.method.post_callback = lambda res: self.post.append(res)
        self.data_model = DataModel(name="dm")
        for node in (self.mode, self.level, self.method):
            self.data_model.root.add_child(node)
        self.data_model._register_nodes(self.data_model.root)

    def record(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        return 0


class TestRequiresArgument:
    def test_defaults_to_empty(self) -> None:
        assert MethodNode(name="m").requires == []
        assert AsyncMethodNode(name="m").requires == []

    def test_is_stored_as_a_list_copy(self) -> None:
        conditions = (cond("mode", EQ, 1),)

        method = MethodNode(name="m", requires=conditions)

        assert method.requires == list(conditions)
        assert isinstance(method.requires, list)

    def test_method_without_requires_is_called_as_before(self) -> None:
        model = Model([])

        result = model.method()

        assert result.error is None
        assert model.calls == [{}]


class TestRejection:
    def test_holding_conditions_let_the_call_through(self) -> None:
        model = Model([cond("mode", EQ, 1), cond("level", GT, 2)])

        model.method()

        assert model.calls == [{}]

    def test_failed_condition_rejects_the_call(self) -> None:
        model = Model([cond("mode", EQ, 2)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert error.node == model.method.qualified_name
        assert "mode == 2 not met" in error.message
        assert str(info.value) == error.message

    def test_rejected_call_has_no_side_effects(self) -> None:
        model = Model([cond("mode", EQ, 2)])
        with (
            patch(
                "machine_data_model.nodes.method_node.trace_method_start"
            ) as start,
            patch(
                "machine_data_model.nodes.method_node.trace_method_end"
            ) as end,
            pytest.raises(MethodPreconditionError),
        ):
            model.method()

        assert model.calls == []
        assert model.pre == []
        assert model.post == []
        start.assert_not_called()
        end.assert_not_called()
        assert model.mode.read() == 1
        assert model.level.read() == 5

    def test_all_conditions_must_hold(self) -> None:
        model = Model([cond("mode", EQ, 1), cond("level", GT, 10)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        assert "level > 10 not met" in info.value.error.message
        assert "mode == 1" not in info.value.error.message
        assert len(info.value.outcomes) == 2

    def test_message_lists_every_unmet_condition(self) -> None:
        model = Model([cond("mode", EQ, 2), cond("level", GT, 10)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        message = info.value.error.message
        assert "mode == 2 not met" in message
        assert "level > 10 not met" in message

    def test_observed_values_are_in_the_field_not_the_message(self) -> None:
        model = Model([cond("mode", EQ, 2)], mode=1)

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.observed == "mode = 1"
        assert "observed" not in error.message
        assert "= 1" not in error.message

    def test_observed_is_bounded(self) -> None:
        text = StringVariableNode(id="s", name="s", value="q" * 5000)
        model = Model([cond("s", EQ, "x")])
        model.data_model.root.add_child(text)
        model.data_model._register_nodes(model.data_model.root)

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        observed = info.value.error.observed
        assert observed is not None
        assert len(observed) <= 256
        assert len(info.value.error.message) < 400

    def test_async_method_inherits_the_check(self) -> None:
        model = Model([cond("mode", EQ, 2)], method_class=AsyncMethodNode)

        with pytest.raises(MethodPreconditionError):
            model.method()

        assert model.calls == []

    def test_conditions_see_the_current_value(self) -> None:
        model = Model([cond("mode", EQ, 2)])
        with pytest.raises(MethodPreconditionError):
            model.method()

        model.mode.write(2)
        model.method()

        assert model.calls == [{}]


class TestNoData:
    def test_variable_without_value_is_no_data(self) -> None:
        model = Model([cond("mode", EQ, 1)])
        model.mode._update_internal_value(None)  # type: ignore[arg-type]

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        assert info.value.error.code is ExecutionErrorCode.NO_DATA
        assert model.calls == []

    def test_remote_variable_never_received_is_no_data(self) -> None:
        model = Model([cond("remote", EQ, 0)])
        remote = NumericalVariableNode(
            id="remote", name="remote", value=0, connector_name="c"
        )
        remote.set_connector(MagicMock())
        model.data_model.root.add_child(remote)
        model.data_model._register_nodes(model.data_model.root)

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.NO_DATA
        assert "no value received yet" in error.message

        remote._remote_subscription_callback(0, MagicMock())
        model.method()
        assert model.calls == [{}]

    def test_failed_wins_over_no_data(self) -> None:
        model = Model([cond("mode", EQ, 1), cond("level", EQ, 1)])
        model.mode._update_internal_value(None)  # type: ignore[arg-type]

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
        assert "level == 1 not met" in error.message
        assert "mode == 1: no value" in error.message


class TestInvalidConfiguration:
    def test_missing_variable(self) -> None:
        model = Model([cond("nope", EQ, 1)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert model.method.qualified_name in error.message
        assert "nope == 1" in error.message
        assert "not found" in error.message
        assert error.node == model.method.qualified_name

    def test_remote_variable_without_connector(self) -> None:
        model = Model([cond("remote", EQ, 0)])
        remote = NumericalVariableNode(
            id="remote", name="remote", value=0, connector_name="missing"
        )
        model.data_model.root.add_child(remote)
        model.data_model._register_nodes(model.data_model.root)

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert "no connector" in error.message

    def test_invalid_condition_stops_the_check(self) -> None:
        model = Model(
            [cond("mode", EQ, 1), cond("nope", EQ, 1), cond("level", EQ, 0)]
        )

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        assert info.value.error.code is (
            ExecutionErrorCode.INVALID_CONFIGURATION
        )
        # Only the conditions before the bad one were evaluated.
        assert len(info.value.outcomes) == 1

    def test_method_outside_a_data_model(self) -> None:
        method = MethodNode(name="m", requires=[cond("mode", EQ, 1)])

        with pytest.raises(MethodPreconditionError) as info:
            method()

        assert info.value.error.code is (
            ExecutionErrorCode.INVALID_CONFIGURATION
        )

    def test_unknown_template_name(self) -> None:
        model = Model([cond("mode", EQ, "${missing}")])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        error = info.value.error
        assert error.code is ExecutionErrorCode.INVALID_CONFIGURATION
        assert "missing" in error.message

    def test_only_the_precondition_error_escapes(self) -> None:
        for conditions in (
            [cond("nope", EQ, 1)],
            [cond("${p}", EQ, 1)],
            [cond("mode", EQ, "${p}")],
        ):
            model = Model(conditions)
            with pytest.raises(MethodPreconditionError):
                model.method()

    def test_error_text_is_sanitized(self) -> None:
        model = Model([cond("no\npe", EQ, "x" * 1000)])

        with pytest.raises(MethodPreconditionError) as info:
            model.method()

        message = info.value.error.message
        assert "\n" not in message
        assert len(message) < 800


class TestParameters:
    def parameters(self) -> list[Any]:
        return [
            StringVariableNode(id="which", name="which", value="mode"),
            NumericalVariableNode(id="want", name="want", value=1),
        ]

    def test_parameter_in_variable_and_rhs_from_keywords(self) -> None:
        model = Model(
            [cond("${which}", EQ, "${want}")], parameters=self.parameters()
        )

        model.method(which="mode", want=1)
        with pytest.raises(MethodPreconditionError):
            model.method(which="mode", want=2)

        assert len(model.calls) == 1

    def test_parameter_from_positional_arguments(self) -> None:
        model = Model(
            [cond("${which}", EQ, "${want}")], parameters=self.parameters()
        )

        model.method("level", 5)
        with pytest.raises(MethodPreconditionError):
            model.method("level", 6)

        assert len(model.calls) == 1

    def test_parameter_default_value_is_used(self) -> None:
        model = Model(
            [cond("${which}", EQ, "${want}")], parameters=self.parameters()
        )

        model.method()

        assert model.calls == [{"which": "mode", "want": 1}]

    def test_parameter_called_context_id_does_not_collide(self) -> None:
        params = [NumericalVariableNode(id="cid", name="context_id", value=1)]
        model = Model([cond("mode", EQ, "${context_id}")], parameters=params)

        model.method()

        assert len(model.calls) == 1
