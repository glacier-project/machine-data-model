from enum import Enum
from typing import Any

from machine_data_model.nodes.composite_method.control_flow_node import (
    ControlFlowNode,
    resolve_value,
)
from machine_data_model.nodes.composite_method.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.variable_node import VariableNode


class WaitConditionOperator(str, Enum):
    """
    Enumeration of wait condition operators.
    """

    EQ = "=="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="


def get_condition_operator(op: str) -> WaitConditionOperator:
    """
    Utility function to get the wait condition operator from a string representation.
    """
    for enum_op in WaitConditionOperator:
        if enum_op.value == op:
            return enum_op
    raise ValueError(f"Invalid operator: {op}")


class WaitConditionNode(ControlFlowNode):
    """
    Represents a wait condition in the control flow graph. When executed, it compares the value
    of a variable with a constant value or another variable.
    It returns immediately if the condition is met, otherwise it subscribes to the variable
    and waits for the value to change.
    """

    def __init__(
        self,
        variable_node: str,
        rhs: Any,
        op: WaitConditionOperator,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """
        Initialize a new WaitConditionNode instance.

        :param variable_node: The identifier of the variable node in the machine data model.
        :param rhs: The right-hand side of the comparison. It can be a constant value or reference to a variable in the scope.
        :param op: The comparison operator.
        """
        super().__init__(variable_node, successors)
        self._rhs = rhs
        self._op = op

    @property
    def rhs(self) -> Any:
        """
        Get the right-hand side of the comparison.

        :return: The right-hand side of the comparison.
        """
        return self._rhs

    @property
    def op(self) -> WaitConditionOperator:
        """
        Get the comparison operator.

        :return: The comparison operator.
        """
        return self._op

    def execute(self, scope: ControlFlowScope) -> bool:
        """
        Execute the wait condition in the control flow graph. If the condition is met, it returns
        immediately. Otherwise, it subscribes to the variable and returns False.

        :param scope: The scope of the control flow graph.
        :return: True if the condition is met, otherwise False.
        """
        ref_variable = self._get_ref_node(scope)
        assert isinstance(ref_variable, VariableNode)

        rhs = resolve_value(self._rhs, scope)
        lhs = ref_variable.read()
        if self._op == WaitConditionOperator.EQ:
            res = lhs == rhs
        elif self._op == WaitConditionOperator.NE:
            res = lhs != rhs
        elif self._op == WaitConditionOperator.LT:
            res = lhs < rhs
        elif self._op == WaitConditionOperator.GT:
            res = lhs > rhs
        elif self._op == WaitConditionOperator.LE:
            res = lhs <= rhs
        elif self._op == WaitConditionOperator.GE:
            res = lhs >= rhs
        else:
            raise ValueError(f"Invalid operator: {self._op}")

        if not res:
            if scope.id() not in ref_variable.get_subscribers():
                ref_variable.subscribe(scope.id())
            return False

        ref_variable.unsubscribe(scope.id())
        return True
