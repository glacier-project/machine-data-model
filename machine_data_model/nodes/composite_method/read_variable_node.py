from machine_data_model.nodes.composite_method.control_flow_node import ControlFlowNode
from machine_data_model.nodes.composite_method.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.variable_node import VariableNode


class ReadVariableNode(ControlFlowNode):
    """
    Represents the read operation of a variable in the machine data model.
    When executed, it reads the value of the variable and stores it in the scope.

    :ivar store_as: The name of the variable used to store the value in the scope.
    """

    def __init__(
        self,
        variable_node: str,
        store_as: str = "",
        successors: list["ControlFlowNode"] | None = None,
    ):
        """
        Initialize a new ReadVariableNode instance.

        :param variable_node: The identifier of the variable node in the machine data model.
        :param store_as: The name of the variable used to store the value in the scope. If not specified, the value is stored with the name of the variable node.
        """
        super().__init__(variable_node, successors)
        self.store_as = store_as

    def execute(self, scope: ControlFlowScope) -> bool:
        """
        Execute the read operation of the variable in the machine data model.

        :param scope: The scope of the control flow graph.
        :return: Returns always True.
        """
        assert isinstance(self._ref_node, VariableNode)
        value = self._ref_node.read()
        name = self.store_as if self.store_as else self._ref_node.name
        scope.set_value(name, value)
        return True
