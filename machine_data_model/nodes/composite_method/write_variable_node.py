from typing import Any

from machine_data_model.nodes.composite_method.control_flow_node import (
    ControlFlowNode,
    resolve_value,
)
from machine_data_model.nodes.composite_method.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.variable_node import VariableNode


class WriteVariableNode(ControlFlowNode):
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

    def execute(self, scope: ControlFlowScope) -> bool:
        """
        Execute the write operation of the variable in the machine data model.

        :param scope: The scope of the control flow graph.
        :return: Returns always True.
        """
        if (
            not isinstance(self._ref_node, VariableNode)
            and self.resolve_callback is not None
        ):
            node_path = resolve_value(self.node, scope)
            self._ref_node = self.resolve_callback(node_path)
        assert isinstance(self._ref_node, VariableNode)
        value = resolve_value(self._value, scope)
        self._ref_node.write(value)
        return True
