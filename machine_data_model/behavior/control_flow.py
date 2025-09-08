from typing import Sequence
from machine_data_model.behavior.control_flow_node import ControlFlowNode
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage


class ControlFlow:
    """
    Represents a control flow graph implementing the logic of a run-time method.
    It consists of a list of control flow nodes that are executed in sequence.
    Difference execution flows are not supported in this version of the control flow graph.

    :ivar _nodes: A list of control flow nodes in the control flow graph.
    """

    def __init__(self, nodes: Sequence[ControlFlowNode] | None = None):
        """
        Initializes a new `ControlFlow` instance.

        :param nodes: A list of control flow nodes in the control flow graph.
        """
        self._nodes = nodes if nodes is not None else []

    def nodes(self) -> Sequence[ControlFlowNode]:
        """
        Gets the list of control flow nodes in the control flow graph.

        :return: The list of control flow nodes in the control flow graph.
        """
        return self._nodes

    def get_current_node(self, scope: ControlFlowScope) -> ControlFlowNode | None:
        """
        Get the current control flow node based on the program counter in the scope of the control flow graph.
        :param scope: The scope of the control flow graph.
        :return: The current control flow node, or None if the program counter is out of bounds.
        """

        # If the cfg is terminated return None
        if not scope.is_active():
            return None

        return self._nodes[scope.get_pc()]

    def execute(self, scope: ControlFlowScope) -> list[FrostMessage]:
        """
        Executes the control flow graph with the specified scope.
        The scope is deactivated when the control flow graph reaches the end of the graph.

        :param scope: The scope of the control flow graph.
        :return: A list of Frost messages to be sent as a result of executing the control flow graph.
        """
        messages: list[FrostMessage] = []
        pc = scope.get_pc()
        while pc < len(self._nodes):
            node = self._nodes[pc]

            result = node.execute(scope)
            if result.messages:
                messages.extend(result.messages)
            if not result.success:
                return messages
            pc += 1
            scope.set_pc(pc)
        scope.deactivate()
        return messages

    # callback for listening for responses in the protocol manager
