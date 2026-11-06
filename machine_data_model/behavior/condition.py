"""Conditions on variables of the machine data model.

A condition compares the value of a variable with a constant or with a value
taken from an execution context. It is a pure predicate: it neither subscribes
to variables nor changes any state.

This module does not import, at module level, node classes that depend on the
behavior package, so it can be imported from anywhere without creating import
cycles.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import operator
from typing import TYPE_CHECKING, Any

from machine_data_model.behavior.execution_context import (
    ExecutionContext,
    contains_template_variables,
    resolve_string_in_context,
    resolve_value,
)

if TYPE_CHECKING:
    from machine_data_model.nodes.data_model_node import DataModelNode
    from machine_data_model.nodes.variable_node import VariableNode


class WaitConditionOperator(str, Enum):
    """Enumeration of condition operators."""

    EQ = "=="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="


_OPERATORS: dict[WaitConditionOperator, Callable[[Any, Any], Any]] = {
    WaitConditionOperator.EQ: operator.eq,
    WaitConditionOperator.NE: operator.ne,
    WaitConditionOperator.LT: operator.lt,
    WaitConditionOperator.GT: operator.gt,
    WaitConditionOperator.LE: operator.le,
    WaitConditionOperator.GE: operator.ge,
}


def get_condition_operator(op: str) -> WaitConditionOperator:
    """Get the condition operator from a string representation.

    Args:
        op (str):
            The string representation of the operator.

    Returns:
        WaitConditionOperator:
            The corresponding WaitConditionOperator enum value.

    Raises:
        ValueError:
            If the operator string is invalid.

    """
    for enum_op in WaitConditionOperator:
        if enum_op.value == op:
            return enum_op
    raise ValueError(f"Invalid operator: {op}")


def compare(op: WaitConditionOperator, lhs: Any, rhs: Any) -> bool:
    """Compare two values with the given operator.

    Args:
        op (WaitConditionOperator):
            The comparison operator.
        lhs (Any):
            The left-hand side of the comparison.
        rhs (Any):
            The right-hand side of the comparison.

    Returns:
        bool:
            The result of the comparison.

    Raises:
        TypeError:
            If the values cannot be ordered by the operator.
        ValueError:
            If the operator is invalid.

    """
    try:
        func = _OPERATORS[op]
    except KeyError:
        raise ValueError(f"Invalid operator: {op}") from None
    return bool(func(lhs, rhs))


class ConditionError(ValueError):
    """Raised when a condition cannot be evaluated because it is misconfigured.

    Unlike a `NO_DATA` outcome, which describes a transient lack of data, this
    error describes a condition that can never be evaluated as written: the
    variable does not exist, is not a variable, or a template cannot be
    resolved.

    Attributes:
        variable (str):
            The (possibly unresolved) path of the variable of the condition.
        message (str):
            A human-readable description of the problem.

    """

    def __init__(self, variable: str, message: str) -> None:
        """Initialize a new ConditionError.

        Args:
            variable (str):
                The path of the variable of the condition.
            message (str):
                A human-readable description of the problem.

        """
        super().__init__(message)
        self.variable = variable
        self.message = message


class ConditionResult(str, Enum):
    """Enumeration of the results of evaluating a condition.

    Attributes:
        OK:
            The condition holds.
        FAILED:
            The condition does not hold.
        NO_DATA:
            The condition cannot be evaluated because a value is unavailable.

    """

    OK = "ok"
    FAILED = "failed"
    NO_DATA = "no_data"


@dataclass(frozen=True)
class ConditionOutcome:
    """Outcome of evaluating a condition.

    Attributes:
        result (ConditionResult):
            The result of the evaluation.
        message (str):
            A human-readable description of the evaluation, for example
            "/plant/conveyor/mode == 2 (observed 1)".
        variable (str):
            The resolved path of the variable.

    """

    result: ConditionResult
    message: str
    variable: str


@dataclass(frozen=True)
class Condition:
    """A comparison between a variable and a value.

    Attributes:
        variable (str):
            The path or id of the variable. It may contain `${name}` templates.
        operator (WaitConditionOperator):
            The comparison operator.
        rhs (Any):
            The right-hand side: a literal or a `${name}` template.

    """

    variable: str
    operator: WaitConditionOperator
    rhs: Any

    def __post_init__(self) -> None:
        """Validate the operator, converting a string to the enum.

        Raises:
            ValueError:
                If the operator is not valid.

        """
        op: Any = self.operator
        if not isinstance(op, WaitConditionOperator):
            object.__setattr__(self, "operator", get_condition_operator(op))

    def _resolve_path(self, scope: ExecutionContext | None) -> str:
        """Resolve the variable path using the scope."""
        if scope is None:
            if contains_template_variables(self.variable):
                raise ConditionError(
                    self.variable,
                    f"variable '{self.variable}' contains a template but no "
                    "scope was given",
                )
            return self.variable
        return str(resolve_string_in_context(self.variable, scope))

    def _resolve_rhs(self, scope: ExecutionContext | None) -> Any:
        """Resolve the right-hand side using the scope."""
        if scope is None:
            if isinstance(self.rhs, str) and contains_template_variables(
                self.rhs
            ):
                raise ConditionError(
                    self.variable,
                    f"right-hand side '{self.rhs}' of '{self.variable}' "
                    "contains a template but no scope was given",
                )
            return self.rhs
        return resolve_value(self.rhs, scope)

    def _resolve_variable(
        self,
        resolve_node: "Callable[[str], DataModelNode | None]",
        scope: ExecutionContext | None,
    ) -> "tuple[str, VariableNode]":
        """Resolve the variable path and look up the variable node.

        Raises:
            ConditionError:
                If the path does not resolve to a variable node.

        """
        from machine_data_model.nodes.variable_node import VariableNode

        path = self._resolve_path(scope)
        node = resolve_node(path)
        if node is None:
            raise ConditionError(path, f"variable '{path}' not found")
        if not isinstance(node, VariableNode):
            raise ConditionError(path, f"node '{path}' is not a variable")
        return path, node

    def evaluate(
        self,
        resolve_node: "Callable[[str], DataModelNode | None]",
        scope: ExecutionContext | None,
        force_remote_read: bool = False,
    ) -> ConditionOutcome:
        """Evaluate the condition.

        Args:
            resolve_node (Callable[[str], DataModelNode | None]):
                Resolves a path to a node of the data model.
            scope (ExecutionContext | None):
                The context used to resolve `${name}` templates.
            force_remote_read (bool):
                If True, remote variables are read from the remote server,
                otherwise their cached value is used.

        Returns:
            ConditionOutcome:
                `NO_DATA` if the variable has no value, has no connector or
                cannot be compared with the right-hand side. Otherwise `OK` or
                `FAILED`.

        Raises:
            ConditionError:
                If the variable is missing or is not a variable, or if a
                template is used without a scope.
            KeyError:
                If a template refers to a name missing in the scope.

        """
        path, variable = self._resolve_variable(resolve_node, scope)
        rhs = self._resolve_rhs(scope)
        text = f"{path} {self.operator.value} {rhs}"

        if variable.is_remote() and not variable.has_connector():
            return ConditionOutcome(
                ConditionResult.NO_DATA,
                f"{text} (no connector)",
                path,
            )

        lhs = variable.read(force_remote_read=force_remote_read)
        if lhs is None:
            return ConditionOutcome(
                ConditionResult.NO_DATA, f"{text} (no value)", path
            )
        try:
            holds = compare(self.operator, lhs, rhs)
        except TypeError:
            return ConditionOutcome(
                ConditionResult.NO_DATA,
                f"{text} (observed {lhs!r}, not comparable)",
                path,
            )
        result = ConditionResult.OK if holds else ConditionResult.FAILED
        return ConditionOutcome(result, f"{text} (observed {lhs})", path)

    def variables(
        self,
        resolve_node: "Callable[[str], DataModelNode | None]",
        scope: ExecutionContext | None,
    ) -> "list[VariableNode]":
        """Return the variables read by this condition.

        Args:
            resolve_node (Callable[[str], DataModelNode | None]):
                Resolves a path to a node of the data model.
            scope (ExecutionContext | None):
                The context used to resolve `${name}` templates.

        Returns:
            list[VariableNode]:
                The variables that would be read. Today a condition reads
                exactly one variable.

        Raises:
            ConditionError:
                If the variable is missing or is not a variable, or if a
                template is used without a scope.

        """
        _, variable = self._resolve_variable(resolve_node, scope)
        return [variable]
