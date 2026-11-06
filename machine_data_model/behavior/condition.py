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
from machine_data_model.behavior.execution_error import sanitize_detail

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


# Longest observed value kept, in characters.
_MAX_OBSERVED = 256

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
            A human-readable description of what must hold and what failed,
            for example "/plant/conveyor/mode == 2 not met". It never contains
            the observed value, so it is safe to send to a peer.
        variable (str):
            The resolved path of the variable.
        observed (str | None):
            The value read from the variable as a bounded `repr`, or None if
            no value was read. For logs and traces only: it is never sent over
            Frost.

    """

    result: ConditionResult
    message: str
    variable: str
    observed: str | None = None


@dataclass(frozen=True)
class ResolvedCondition:
    """A condition whose templates and variable path were resolved.

    Attributes:
        path (str):
            The resolved path of the variable.
        variable (VariableNode):
            The variable node the path resolves to.
        rhs (Any):
            The resolved right-hand side.

    """

    path: str
    variable: "VariableNode"
    rhs: Any


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

    def resolve(
        self,
        resolve_node: "Callable[[str], DataModelNode | None]",
        scope: ExecutionContext | None,
    ) -> ResolvedCondition:
        """Resolve the variable and the right-hand side.

        Resolving once lets a caller both subscribe to the variable and
        evaluate the condition on it (`evaluate_on`).

        Args:
            resolve_node (Callable[[str], DataModelNode | None]):
                Resolves a path to a node of the data model.
            scope (ExecutionContext | None):
                The context used to resolve `${name}` templates.

        Returns:
            ResolvedCondition:
                The resolved path, variable node and right-hand side.

        Raises:
            ConditionError:
                If the variable is missing or is not a variable, or if a
                template is used without a scope.
            KeyError:
                If a template refers to a name missing in the scope.

        """
        path, variable = self._resolve_variable(resolve_node, scope)
        return ResolvedCondition(path, variable, self._resolve_rhs(scope))

    def evaluate(
        self,
        resolve_node: "Callable[[str], DataModelNode | None]",
        scope: ExecutionContext | None,
        force_remote_read: bool = False,
    ) -> ConditionOutcome:
        """Evaluate the condition: `resolve` followed by `evaluate_on`.

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
                See `evaluate_on`.

        Raises:
            ConditionError:
                If the variable is missing or is not a variable, or if a
                template is used without a scope.
            KeyError:
                If a template refers to a name missing in the scope.

        """
        resolved = self.resolve(resolve_node, scope)
        return self.evaluate_on(
            resolved.variable,
            resolved.rhs,
            force_remote_read=force_remote_read,
            path=resolved.path,
        )

    def evaluate_on(
        self,
        variable: "VariableNode",
        rhs: Any,
        force_remote_read: bool = False,
        path: str | None = None,
    ) -> ConditionOutcome:
        """Evaluate the condition on an already resolved variable.

        Args:
            variable (VariableNode):
                The variable to compare.
            rhs (Any):
                The resolved right-hand side.
            force_remote_read (bool):
                If True, remote variables are read from the remote server,
                otherwise their cached value is used.
            path (str | None):
                The path used in messages. Defaults to the qualified name of
                the variable.

        Returns:
            ConditionOutcome:
                `NO_DATA` if the variable has no value, a remote variable never
                received one, the variable cannot
                be read (`OSError`, including `ConnectionError` and
                `TimeoutError`) or cannot be compared with the right-hand
                side. Otherwise `OK` or `FAILED`.

        Raises:
            ConditionError:
                If the variable is remote and has no connector.

        """
        if path is None:
            path = variable.qualified_name
        text = f"{path} {self.operator.value} {rhs}"

        if variable.is_remote() and not variable.has_connector():
            # A configuration problem, not a transient lack of data: there is
            # nothing to wait for.
            raise ConditionError(
                path, f"variable '{path}' is remote but has no connector"
            )

        try:
            lhs = variable.read(force_remote_read=force_remote_read)
        except OSError as error:
            # Covers ConnectionError and TimeoutError: a transient lack of
            # data. Any other exception is a programming error and propagates.
            return ConditionOutcome(
                ConditionResult.NO_DATA,
                f"{text}: read failed ({type(error).__name__})",
                path,
            )
        if not variable.has_received_value():
            # The cached value is still the default of the constructor: a
            # guard must not pass (or fail) on a value nobody ever sent.
            return ConditionOutcome(
                ConditionResult.NO_DATA,
                f"{text}: no value received yet",
                path,
            )
        if lhs is None:
            return ConditionOutcome(
                ConditionResult.NO_DATA, f"{text}: no value", path
            )
        observed = sanitize_detail(repr(lhs), _MAX_OBSERVED)
        try:
            holds = compare(self.operator, lhs, rhs)
        except TypeError:
            return ConditionOutcome(
                ConditionResult.NO_DATA,
                f"{text}: not comparable",
                path,
                observed,
            )
        if holds:
            return ConditionOutcome(
                ConditionResult.OK, f"{text} met", path, observed
            )
        return ConditionOutcome(
            ConditionResult.FAILED, f"{text} not met", path, observed
        )

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
