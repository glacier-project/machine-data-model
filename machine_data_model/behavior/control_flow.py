from typing import Sequence
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
)
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.tracing import trace_control_flow_start, trace_control_flow_end


class ControlFlow:
    """
    Represents a control flow graph for a run-time method.

    It consists of a list of control flow nodes that are executed in sequence.

    Attributes:
        _nodes (Sequence[ControlFlowNode]): A list of control flow nodes.
    """

    def __init__(self, nodes: Sequence[ControlFlowNode] | None = None):
        """
        Initializes a new `ControlFlow` instance.

        Args:
            nodes (Sequence[ControlFlowNode] | None): A list of control flow nodes.
        """
        self._nodes = nodes if nodes is not None else []

    def nodes(self) -> Sequence[ControlFlowNode]:
        """
        Gets the list of control flow nodes.

        Returns:
            Sequence[ControlFlowNode]: The list of control flow nodes.
        """
        return self._nodes

    def get_current_node(self, scope: ControlFlowScope) -> ControlFlowNode | None:
        """
        Gets the current control flow node based on the program counter in the scope.

        Args:
            scope (ControlFlowScope): The scope of the control flow graph.

        Returns:
            ControlFlowNode | None: The current control flow node, or None if the program counter is out of bounds.
        """

        # If the cfg is terminated return None
        if not scope.is_active():
            return None

        return self._nodes[scope.get_pc()]

    def execute(self, scope: ControlFlowScope) -> list[FrostMessage]:
        """
        Executes the control flow graph with the specified scope.

        The scope is deactivated when the control flow graph reaches the end.

        Args:
            scope (ControlFlowScope): The scope of the control flow graph.

        Returns:
            list[FrostMessage]: A list of Frost messages to be sent.
        """

        data_model_id = "NO DATA MODEL"  # TODO: fix this

        # Trace control flow start.
        trace_control_flow_start(
            control_flow_id=scope.id(),
            total_steps=len(self._nodes),
            source=scope.id(),
            data_model_id=data_model_id,
        )

        messages: list[FrostMessage] = []
        pc = scope.get_pc()
        executed_steps = 0

        while pc < len(self._nodes):
            node = self._nodes[pc]
            # TODO: fix me here
            # if contains_template_variables(node.node):
            #     node.node = scope.get_value(node.node)

            result = node.execute(scope)
            executed_steps += 1

            if result.messages:
                messages.extend(result.messages)
            if not result.success:
                # Trace control flow end (failure)
                trace_control_flow_end(
                    control_flow_id=scope.id(),
                    success=False,
                    executed_steps=executed_steps,
                    final_pc=pc,
                    source=scope.id(),
                    data_model_id=data_model_id,
                )
                return messages
            pc += 1
            scope.set_pc(pc)

        scope.deactivate()

        # Trace control flow end (success)
        trace_control_flow_end(
            control_flow_id=scope.id(),
            success=True,
            executed_steps=executed_steps,
            final_pc=pc,
            source=scope.id(),
            data_model_id=data_model_id,
        )

        return messages

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, ControlFlow):
            return False

        if len(self._nodes) != len(other._nodes):
            return False

        for i, node in enumerate(self._nodes):
            if node != other._nodes[i]:
                return False

        return True
