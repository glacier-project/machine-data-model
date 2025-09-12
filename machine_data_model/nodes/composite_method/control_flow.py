from machine_data_model.nodes.composite_method.control_flow_node import ControlFlowNode
from machine_data_model.nodes.composite_method.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.composite_method.control_flow_node import (
    is_template_variable,
)


class ControlFlow:
    """
    Represents a control flow graph implementing the logic of a run-time method.
    It consists of a list of control flow nodes that are executed in sequence.
    Difference execution flows are not supported in this version of the control flow graph.

    :ivar _nodes: A list of control flow nodes in the control flow graph.
    """

    def __init__(self, nodes: list[ControlFlowNode] | None = None):
        """
        Initializes a new `ControlFlow` instance.

        :param nodes: A list of control flow nodes in the control flow graph.
        """
        self._nodes = nodes if nodes is not None else []

    def nodes(self) -> list[ControlFlowNode]:
        """
        Gets the list of control flow nodes in the control flow graph.

        :return: The list of control flow nodes in the control flow graph.
        """
        return self._nodes

    def execute(self, scope: ControlFlowScope) -> None:
        """
        Executes the control flow graph with the specified scope.
        The scope is deactivated when the control flow graph reaches the end of the graph.

        :param scope: The scope of the control flow graph.
        """
        pc = scope.get_pc()
        while pc < len(self._nodes):
            node = self._nodes[pc]
            if is_template_variable(node.node):
                node.node = scope.resolve_template_variable(node.node)
            if not node.execute(scope):
                return
            pc += 1
            scope.set_pc(pc)
        scope.deactivate()
