from typing import Any

from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    resolve_value,
    LocalExecutionNode,
)
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.variable_node import VariableNode


class WriteVariableNode(LocalExecutionNode):
    """
    Represents the write operation of a variable in the machine data model.
    When executed, it writes the value to the variable in the machine data model.

    :ivar value: The value to write to the variable.
    """

    def __init__(
        self,
        variable_node: str,
        value: Any,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """
        Initialize a new WriteVariableNode instance.

        :param variable_node: The identifier of the variable node in the machine data model.
        :param value: The value to write to the variable. It can be a constant value or reference to a variable in the scope.
        """
        super().__init__(variable_node, successors)
        self._value = value

    @property
    def value(self) -> Any:
        """
        Get the value to write to the variable.

        :return: The value to write to the variable.
        """
        return self._value

    def execute(self, scope: ControlFlowScope) -> bool:
        """
        Execute the write operation of the variable in the machine data model.

        :param scope: The scope of the control flow graph.
        :return: Returns always True.
        """
        ref_variable = self._get_ref_node(scope)
        assert isinstance(ref_variable, VariableNode)

        value = resolve_value(self._value, scope)
        ref_variable.write(value)
        return True
