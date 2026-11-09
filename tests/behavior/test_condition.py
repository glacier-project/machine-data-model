"""Unit tests for `Condition`, `compare` and module import isolation."""

from collections.abc import Callable
import operator as py_operator
import subprocess
import sys
from typing import Any
from unittest.mock import MagicMock
import uuid

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    ConditionError,
    ConditionResult,
    ResolvedCondition,
    WaitConditionOperator,
    compare,
    get_condition_operator,
)
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
)
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
    VariableNode,
)

OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "==": py_operator.eq,
    "!=": py_operator.ne,
    "<": py_operator.lt,
    ">": py_operator.gt,
    "<=": py_operator.le,
    ">=": py_operator.ge,
}


def resolver_for(
    *nodes: DataModelNode,
) -> Callable[[str], DataModelNode | None]:
    by_name = {node.name: node for node in nodes}
    return lambda path: by_name.get(path)


def scope(**values: Any) -> ExecutionContext:
    context = ExecutionContext(str(uuid.uuid4()))
    for key, value in values.items():
        context.set_value(key, value)
    return context


class TestCompare:
    @pytest.mark.parametrize("op", list(OPERATORS))
    @pytest.mark.parametrize(
        "lhs, rhs",
        [
            (1, 2),
            (2, 2),
            (3, 2),
            (1.5, 1.5),
            (1, 1.0),
            ("a", "b"),
            ("b", "b"),
            (False, True),
            (True, True),
        ],
    )
    def test_matches_python_operators(
        self, op: str, lhs: Any, rhs: Any
    ) -> None:
        result = compare(get_condition_operator(op), lhs, rhs)

        assert result is OPERATORS[op](lhs, rhs)
        assert isinstance(result, bool)

    @pytest.mark.parametrize("op", ["<", ">", "<=", ">="])
    def test_ordering_mixed_types_raises_type_error(self, op: str) -> None:
        with pytest.raises(TypeError):
            compare(get_condition_operator(op), "a", 1)
        with pytest.raises(TypeError):
            compare(get_condition_operator(op), None, 1)

    def test_equality_mixed_types_does_not_raise(self) -> None:
        assert not compare(WaitConditionOperator.EQ, "1", 1)
        assert compare(WaitConditionOperator.NE, "1", 1)
        assert compare(WaitConditionOperator.EQ, None, None)

    def test_invalid_operator(self) -> None:
        with pytest.raises(ValueError):
            compare("=<", 1, 2)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            get_condition_operator("=<")


class TestEvaluate:
    def test_ok(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        outcome = cond.evaluate(resolver_for(var), None)

        assert outcome.result is ConditionResult.OK
        assert outcome.variable == "mode"
        assert outcome.message == "mode == 2 met"
        assert outcome.observed == "2"

    def test_failed_message_has_no_observed_value(self) -> None:
        var = NumericalVariableNode(name="mode", value=1)
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        outcome = cond.evaluate(resolver_for(var), None)

        assert outcome.result is ConditionResult.FAILED
        assert outcome.message == "mode == 2 not met"
        assert "1" not in outcome.message.replace("mode == 2", "")
        assert outcome.observed == "1"

    def test_message_sanitizes_the_right_hand_side(self) -> None:
        var = StringVariableNode(name="mode", value="a")
        rhs = "x\ny\x1b[0m" + "z" * 500
        cond = Condition("mode", WaitConditionOperator.EQ, rhs)

        outcome = cond.evaluate(resolver_for(var), None)

        assert "\n" not in outcome.message
        assert "\x1b" not in outcome.message
        assert outcome.message.startswith("mode == x y [0m")
        assert outcome.message.endswith("... not met")
        assert len(outcome.message) < 120

    def test_message_sanitizes_the_path(self) -> None:
        var = StringVariableNode(name="mo\nde", value="a")
        cond = Condition("mo\nde", WaitConditionOperator.EQ, "a")

        outcome = cond.evaluate(resolver_for(var), None)

        assert outcome.message == "mo de == a met"
        # The path field stays the real identifier.
        assert outcome.variable == "mo\nde"

    def test_no_data_has_no_observed_value(self) -> None:
        var = NumericalVariableNode(name="mode", value=0)
        var._update_internal_value(None)  # type: ignore[arg-type]

        outcome = Condition("mode", WaitConditionOperator.EQ, 2).evaluate(
            resolver_for(var), None
        )

        assert outcome.message == "mode == 2: no value"
        assert outcome.observed is None

    def test_not_comparable_keeps_value_out_of_message(self) -> None:
        var = StringVariableNode(name="mode", value="secret-abc")

        outcome = Condition("mode", WaitConditionOperator.GT, 3).evaluate(
            resolver_for(var), None
        )

        assert outcome.result is ConditionResult.NO_DATA
        assert outcome.message == "mode > 3: not comparable"
        assert outcome.observed == "'secret-abc'"

    def test_observed_is_bounded_and_clean(self) -> None:
        var = StringVariableNode(name="mode", value="a\nb" + "z" * 5000)

        outcome = Condition("mode", WaitConditionOperator.EQ, "x").evaluate(
            resolver_for(var), None
        )

        assert outcome.observed is not None
        assert len(outcome.observed) == 256
        assert outcome.observed.endswith("...")
        assert "\n" not in outcome.observed
        assert len(outcome.message) < 100

    def test_no_data_for_none_value(self) -> None:
        var = NumericalVariableNode(name="mode", value=0)
        var._update_internal_value(None)  # type: ignore[arg-type]
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        outcome = cond.evaluate(resolver_for(var), None)

        assert outcome.result is ConditionResult.NO_DATA

    @pytest.mark.parametrize("op", ["<", ">", "<=", ">="])
    def test_no_data_for_uncomparable_values(self, op: str) -> None:
        var = StringVariableNode(name="mode", value="abc")
        cond = Condition("mode", get_condition_operator(op), 3)

        outcome = cond.evaluate(resolver_for(var), None)

        assert outcome.result is ConditionResult.NO_DATA

    def test_missing_variable_raises_condition_error(self) -> None:
        cond = Condition("nope", WaitConditionOperator.EQ, 2)

        with pytest.raises(ConditionError) as info:
            cond.evaluate(resolver_for(), None)

        assert info.value.variable == "nope"
        assert "nope" in info.value.message
        assert isinstance(info.value, ValueError)

    def test_non_variable_node_raises_condition_error(self) -> None:
        folder = FolderNode(name="mode")
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        with pytest.raises(ConditionError) as info:
            cond.evaluate(resolver_for(folder), None)

        assert info.value.variable == "mode"
        assert "not a variable" in info.value.message

    def test_remote_variable_without_connector_raises_condition_error(
        self,
    ) -> None:
        var = NumericalVariableNode(
            name="mode", value=2, connector_name="missing"
        )
        assert var.is_remote()
        assert not var.has_connector()
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        with pytest.raises(ConditionError) as info:
            cond.evaluate(resolver_for(var), None)

        assert info.value.variable == "mode"
        assert "no connector" in info.value.message

    def test_remote_variable_without_value_is_no_data(self) -> None:
        """A guard must not pass on the constructor default."""
        var = NumericalVariableNode(name="mode", value=0, connector_name="c")
        var.set_connector(MagicMock())
        assert var.is_remote()
        assert var.has_connector()

        same = Condition("mode", WaitConditionOperator.EQ, 0)
        other = Condition("mode", WaitConditionOperator.EQ, 2)

        for cond in (same, other):
            outcome = cond.evaluate(resolver_for(var), None)
            assert outcome.result is ConditionResult.NO_DATA
            assert outcome.message.endswith(": no value received yet")
            assert outcome.observed is None

    def test_remote_variable_is_evaluated_after_a_callback(self) -> None:
        var = NumericalVariableNode(name="mode", value=0, connector_name="c")
        var.set_connector(MagicMock())
        var._remote_subscription_callback(2, MagicMock())

        ok = Condition("mode", WaitConditionOperator.EQ, 2)
        failed = Condition("mode", WaitConditionOperator.EQ, 0)

        assert ok.evaluate(resolver_for(var), None).result is (
            ConditionResult.OK
        )
        assert failed.evaluate(resolver_for(var), None).result is (
            ConditionResult.FAILED
        )

    def test_forced_read_that_receives_a_value_is_evaluated(self) -> None:
        var = NumericalVariableNode(name="mode", value=0, connector_name="c")
        connector = MagicMock()
        connector.read_node_value.return_value = 2
        var.set_connector(connector)
        var.set_remote_path("ns=1")
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        cached = cond.evaluate(resolver_for(var), None)
        forced = cond.evaluate(resolver_for(var), None, force_remote_read=True)
        after = cond.evaluate(resolver_for(var), None)

        assert cached.result is ConditionResult.NO_DATA
        assert forced.result is ConditionResult.OK
        assert after.result is ConditionResult.OK

    def test_forced_read_without_value_stays_no_data(self) -> None:
        var = NumericalVariableNode(name="mode", value=0, connector_name="c")
        connector = MagicMock()
        connector.read_node_value.return_value = None
        var.set_connector(connector)
        var.set_remote_path("ns=1")

        outcome = Condition("mode", WaitConditionOperator.EQ, 0).evaluate(
            resolver_for(var), None, force_remote_read=True
        )

        assert outcome.result is ConditionResult.NO_DATA

    def test_property_of_remote_object_never_passes_on_default(self) -> None:
        prop = NumericalVariableNode(name="prop", value=0)
        obj = ObjectVariableNode(
            name="obj", properties={"prop": prop}, connector_name="c"
        )
        obj.set_connector(MagicMock())
        assert not prop.is_remote()
        cond = Condition("prop", WaitConditionOperator.EQ, 0)

        before = cond.evaluate(resolver_for(prop), None)
        obj._remote_subscription_callback({"prop": 0}, MagicMock())
        after = cond.evaluate(resolver_for(prop), None)

        assert before.result is ConditionResult.NO_DATA
        assert after.result is ConditionResult.OK

    def test_cached_value_used_unless_remote_read_is_forced(self) -> None:
        reads: list[bool] = []

        class Spy(NumericalVariableNode):
            def read(self, force_remote_read: bool = True) -> Any:
                reads.append(force_remote_read)
                return super().read(force_remote_read)

        var = Spy(name="mode", value=2)
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        cond.evaluate(resolver_for(var), None)
        cond.evaluate(resolver_for(var), None, force_remote_read=True)

        assert reads == [False, True]

    def test_evaluate_has_no_side_effects(self) -> None:
        var = NumericalVariableNode(name="mode", value=1)
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        cond.evaluate(resolver_for(var), scope())

        assert var.get_subscriptions() == []
        assert var.read() == 1


class TestReadFailures:
    @staticmethod
    def failing_variable(error: Exception) -> NumericalVariableNode:
        class Failing(NumericalVariableNode):
            def read(self, force_remote_read: bool = True) -> Any:
                raise error

        return Failing(name="mode", value=1)

    @pytest.mark.parametrize(
        "error",
        [
            ConnectionError("down"),
            TimeoutError("slow"),
            ConnectionResetError("reset"),
            BrokenPipeError("pipe"),
        ],
    )
    def test_connection_and_timeout_errors_give_no_data(
        self, error: OSError
    ) -> None:
        var = self.failing_variable(error)
        cond = Condition("mode", WaitConditionOperator.EQ, 1)

        outcome = cond.evaluate(resolver_for(var), None, force_remote_read=True)

        assert outcome.result is ConditionResult.NO_DATA
        assert outcome.message == (
            f"mode == 1: read failed ({type(error).__name__})"
        )
        assert outcome.observed is None
        # The text of the exception is not part of the message.
        assert str(error) not in outcome.message

    @pytest.mark.parametrize(
        "error",
        [
            RuntimeError("bug"),
            AssertionError("bug"),
            KeyError("k"),
            OSError("io"),
            FileNotFoundError("missing"),
            PermissionError("denied"),
        ],
    )
    def test_other_errors_propagate(self, error: Exception) -> None:
        var = self.failing_variable(error)
        cond = Condition("mode", WaitConditionOperator.EQ, 1)

        with pytest.raises(type(error)):
            cond.evaluate(resolver_for(var), None)

    def test_evaluate_on_also_catches_timeouts(self) -> None:
        var = self.failing_variable(TimeoutError("slow"))

        outcome = Condition("mode", WaitConditionOperator.EQ, 1).evaluate_on(
            var, 1, path="mode"
        )

        assert outcome.result is ConditionResult.NO_DATA


class TestTemplates:
    def test_template_in_rhs(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("mode", WaitConditionOperator.EQ, "${wanted}")

        ok = cond.evaluate(resolver_for(var), scope(wanted=2))
        failed = cond.evaluate(resolver_for(var), scope(wanted=3))

        assert ok.result is ConditionResult.OK
        assert failed.result is ConditionResult.FAILED

    def test_template_in_variable(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("${which}", WaitConditionOperator.EQ, 2)

        outcome = cond.evaluate(resolver_for(var), scope(which="mode"))

        assert outcome.result is ConditionResult.OK
        assert outcome.variable == "mode"

    def test_template_in_both(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("${which}", WaitConditionOperator.GE, "${wanted}")

        outcome = cond.evaluate(
            resolver_for(var), scope(which="mode", wanted=1)
        )

        assert outcome.result is ConditionResult.OK

    def test_missing_template_key_raises_key_error(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)

        with pytest.raises(KeyError):
            Condition("mode", WaitConditionOperator.EQ, "${x}").evaluate(
                resolver_for(var), scope()
            )
        with pytest.raises(KeyError):
            Condition("${x}", WaitConditionOperator.EQ, 2).evaluate(
                resolver_for(var), scope()
            )

    def test_template_without_scope_raises_condition_error(self) -> None:
        var = StringVariableNode(name="mode", value="${wanted}")

        with pytest.raises(ConditionError) as in_rhs:
            Condition("mode", WaitConditionOperator.EQ, "${wanted}").evaluate(
                resolver_for(var), None
            )
        with pytest.raises(ConditionError) as in_variable:
            Condition("${which}", WaitConditionOperator.EQ, 1).evaluate(
                resolver_for(var), None
            )
        with pytest.raises(ConditionError):
            Condition("${which}", WaitConditionOperator.EQ, 1).variables(
                resolver_for(var), None
            )

        assert in_rhs.value.variable == "mode"
        assert in_variable.value.variable == "${which}"

    def test_non_string_rhs_needs_no_scope(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        assert cond.evaluate(resolver_for(var), None).result is (
            ConditionResult.OK
        )


class TestVariables:
    def test_returns_the_variable(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        found: list[VariableNode] = cond.variables(resolver_for(var), None)

        assert found == [var]
        assert found[0] is var

    def test_resolves_templated_path(self) -> None:
        var = NumericalVariableNode(name="mode", value=2)
        cond = Condition("${which}", WaitConditionOperator.EQ, 2)

        found = cond.variables(resolver_for(var), scope(which="mode"))

        assert found[0] is var

    def test_does_not_read_the_variable(self) -> None:
        reads: list[bool] = []

        class Spy(NumericalVariableNode):
            def read(self, force_remote_read: bool = True) -> Any:
                reads.append(force_remote_read)
                return super().read(force_remote_read)

        var = Spy(name="mode", value=2)

        Condition("mode", WaitConditionOperator.EQ, 2).variables(
            resolver_for(var), None
        )

        assert reads == []

    def test_raises_for_missing_or_non_variable(self) -> None:
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        with pytest.raises(ConditionError):
            cond.variables(resolver_for(), None)
        with pytest.raises(ConditionError):
            cond.variables(resolver_for(FolderNode(name="mode")), None)


class TestResolveAndEvaluateOn:
    def test_resolve_returns_path_variable_and_rhs(self) -> None:
        var = NumericalVariableNode(id="mode", name="mode", value=1)
        cond = Condition("${which}", WaitConditionOperator.EQ, "${want}")

        resolved = cond.resolve(resolver_for(var), scope(which="mode", want=2))

        assert isinstance(resolved, ResolvedCondition)
        assert resolved.path == "mode"
        assert resolved.variable is var
        assert resolved.rhs == 2

    def test_resolve_raises_like_evaluate(self) -> None:
        cond = Condition("missing", WaitConditionOperator.EQ, 1)
        with pytest.raises(ConditionError):
            cond.resolve(resolver_for(), None)
        with pytest.raises(ConditionError):
            cond.resolve(resolver_for(FolderNode(name="missing")), None)
        with pytest.raises(ConditionError):
            Condition("${v}", WaitConditionOperator.EQ, 1).resolve(
                resolver_for(), None
            )
        with pytest.raises(KeyError):
            Condition("mode", WaitConditionOperator.EQ, "${x}").resolve(
                resolver_for(NumericalVariableNode(id="m", name="mode")),
                scope(),
            )

    def test_resolved_condition_is_frozen(self) -> None:
        var = NumericalVariableNode(id="mode", name="mode", value=1)
        resolved = Condition("mode", WaitConditionOperator.EQ, 1).resolve(
            resolver_for(var), None
        )
        with pytest.raises(AttributeError):
            resolved.path = "x"  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("value", "rhs", "result"),
        [
            (2, 2, ConditionResult.OK),
            (1, 2, ConditionResult.FAILED),
            (None, 2, ConditionResult.NO_DATA),
        ],
    )
    def test_evaluate_on_matches_evaluate(
        self, value: Any, rhs: Any, result: ConditionResult
    ) -> None:
        var = NumericalVariableNode(id="mode", name="mode", value=value)
        cond = Condition("mode", WaitConditionOperator.EQ, rhs)

        direct = cond.evaluate(resolver_for(var), None)
        on = cond.evaluate_on(var, rhs, path="mode")

        assert on == direct
        assert on.result is result

    def test_evaluate_on_default_path_is_qualified_name(self) -> None:
        var = NumericalVariableNode(id="mode", name="mode", value=1)

        outcome = Condition("mode", WaitConditionOperator.EQ, 1).evaluate_on(
            var, 1
        )

        assert outcome.variable == var.qualified_name

    def test_evaluate_on_no_connector_raises_condition_error(self) -> None:
        var = NumericalVariableNode(name="r", value=1, connector_name="missing")

        with pytest.raises(ConditionError) as info:
            Condition("r", WaitConditionOperator.EQ, 1).evaluate_on(
                var, 1, path="r"
            )

        assert info.value.variable == "r"
        assert (
            info.value.message == "variable 'r' is remote but has no connector"
        )


class TestNoConnectorAgrees:
    """resolve, variables and evaluate raise the same error."""

    @staticmethod
    def setup() -> tuple[Condition, NumericalVariableNode]:
        var = NumericalVariableNode(
            name="mode", value=2, connector_name="missing"
        )
        assert var.is_remote() and not var.has_connector()
        return Condition("mode", WaitConditionOperator.EQ, 2), var

    @pytest.mark.parametrize("method", ["resolve", "variables", "evaluate"])
    def test_same_condition_error(self, method: str) -> None:
        cond, var = self.setup()

        with pytest.raises(ConditionError) as info:
            getattr(cond, method)(resolver_for(var), None)

        assert info.value.variable == "mode"
        assert info.value.message == (
            "variable 'mode' is remote but has no connector"
        )

    def test_templated_path_reports_the_resolved_path(self) -> None:
        _, var = self.setup()
        cond = Condition("${which}", WaitConditionOperator.EQ, 2)

        with pytest.raises(ConditionError) as info:
            cond.resolve(resolver_for(var), scope(which="mode"))

        assert info.value.variable == "mode"

    def test_remote_variable_with_connector_still_resolves(self) -> None:
        cond, var = self.setup()
        var.set_connector(MagicMock())

        assert cond.resolve(resolver_for(var), None).variable is var
        assert cond.variables(resolver_for(var), None) == [var]


class TestDataclasses:
    def test_condition_is_frozen_and_comparable(self) -> None:
        cond = Condition("mode", WaitConditionOperator.EQ, 2)

        assert cond == Condition("mode", WaitConditionOperator.EQ, 2)
        assert cond != Condition("mode", WaitConditionOperator.NE, 2)
        with pytest.raises(AttributeError):
            cond.rhs = 3  # type: ignore[misc]

    def test_operator_string_is_converted(self) -> None:
        cond = Condition("mode", ">=", 2)  # type: ignore[arg-type]

        assert cond.operator is WaitConditionOperator.GE
        assert cond == Condition("mode", WaitConditionOperator.GE, 2)

    def test_invalid_operator_raises_at_construction(self) -> None:
        with pytest.raises(ValueError):
            Condition("mode", "=<", 2)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            Condition("mode", None, 2)  # type: ignore[arg-type]

    def test_execution_error(self) -> None:
        error = ExecutionError(ExecutionErrorCode.NO_DATA, "no value", "a/b")

        assert error.code is ExecutionErrorCode.NO_DATA
        assert error.node == "a/b"
        assert ExecutionError(ExecutionErrorCode.TIMEOUT, "t").node is None
        assert {c.value for c in ExecutionErrorCode} == {
            "precondition_not_met",
            "no_data",
            "timeout",
            "invalid_configuration",
            "remote_error",
            "unexpected_error",
        }


class TestReExports:
    def test_local_execution_node_reexports(self) -> None:
        from machine_data_model.behavior import local_execution_node as lne

        assert lne.WaitConditionOperator is WaitConditionOperator
        assert lne.get_condition_operator is get_condition_operator


@pytest.mark.parametrize(
    "module",
    [
        "machine_data_model.behavior.execution_error",
        "machine_data_model.behavior.condition",
        "machine_data_model.nodes.method_node",
        "machine_data_model.behavior.local_execution_node",
        "machine_data_model.behavior.control_flow_node",
        "machine_data_model.nodes.composite_method.composite_method_node",
        "machine_data_model.data_model",
    ],
)
def test_module_imports_first_in_fresh_interpreter(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import {module}"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


class TestInvalidOperatorMessage:
    VALID = "==, !=, <, >, <=, >="

    def test_get_condition_operator_lists_the_valid_ones(self) -> None:
        with pytest.raises(ValueError) as info:
            get_condition_operator("~=")

        assert str(info.value) == (
            f"Invalid operator: ~=. Valid operators: {self.VALID}"
        )

    def test_condition_constructor_lists_the_valid_ones(self) -> None:
        with pytest.raises(ValueError, match="Valid operators: =="):
            Condition("v", "=>", 1)  # type: ignore[arg-type]

    def test_compare_lists_the_valid_ones(self) -> None:
        with pytest.raises(ValueError) as info:
            compare("??", 1, 2)  # type: ignore[arg-type]

        assert f"Valid operators: {self.VALID}" in str(info.value)

    def test_every_valid_operator_is_listed(self) -> None:
        with pytest.raises(ValueError) as info:
            get_condition_operator("x")

        for operator in WaitConditionOperator:
            assert operator.value in str(info.value)

    def test_bad_operator_text_is_sanitized_and_bounded(self) -> None:
        bad = "a\nb\x1b" + "z" * 500

        with pytest.raises(ValueError) as info:
            get_condition_operator(bad)

        message = str(info.value)
        assert "\n" not in message
        assert "\x1b" not in message
        assert len(message) < 150


class TestTemplatesInContainerRhs:
    @pytest.mark.parametrize(
        "rhs",
        [
            ["${a}"],
            ("x", "${a}"),
            {"k": "${a}"},
            {"${a}": 1},
            {"nested": [1, {"deep": "pre ${a} post"}]},
            {"${a}"},
        ],
        ids=["list", "tuple", "dict-value", "dict-key", "nested", "set"],
    )
    def test_template_inside_a_container_is_rejected(self, rhs: Any) -> None:
        with pytest.raises(ValueError) as info:
            Condition("v", WaitConditionOperator.EQ, rhs)

        message = str(info.value)
        assert "template" in message
        assert "only resolved in a string rhs" in message

    @pytest.mark.parametrize(
        "rhs",
        [1, 2.5, None, True, [], {}, [1, 2], {"k": "v"}, ("a", "b"), "${a}"],
        ids=repr,
    )
    def test_other_values_are_accepted(self, rhs: Any) -> None:
        Condition("v", WaitConditionOperator.EQ, rhs)

    def test_message_is_sanitized_and_bounded(self) -> None:
        with pytest.raises(ValueError) as info:
            Condition("v\n", WaitConditionOperator.EQ, ["${a}\n" + "z" * 500])

        message = str(info.value)
        assert "\n" not in message
        assert len(message) < 400

    def test_method_requires_rejects_it_at_construction(self) -> None:
        from machine_data_model.nodes.method_node import MethodNode

        with pytest.raises(ValueError, match="template"):
            MethodNode(
                name="m",
                requires=[
                    Condition("v", WaitConditionOperator.EQ, ["${a}"]),
                ],
            )

    def test_yaml_builder_rejects_it(self) -> None:
        import yaml

        from machine_data_model.builder.data_model_builder import (
            _register_yaml_constructors,
        )

        _register_yaml_constructors()

        with pytest.raises(ValueError, match=r"requires\[0\].*template"):
            yaml.safe_load(
                '!!MethodNode\nname: "m"\nrequires:\n'
                '  - {variable: "v", operator: "==", rhs: ["${a}"]}\n'
            )
