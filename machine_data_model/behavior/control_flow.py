from typing import TYPE_CHECKING, Sequence
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
)
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.tracing import trace_control_flow_start, trace_control_flow_end

if TYPE_CHECKING:
    from machine_data_model.nodes.composite_method.composite_method_node import (
        CompositeMethodNode,
    )


class ControlFlow:
    """
    Represents a control flow graph implementing the logic of a run-time method.
    It consists of a list of control flow nodes that are executed in sequence.
    Difference execution flows are not supported in this version of the control flow graph.

    :ivar _nodes: A list of control flow nodes in the control flow graph.
    :ivar _composite_method_node: The composite method node that owns this control flow graph.
    """

    def __init__(
        self,
        nodes: Sequence[ControlFlowNode] | None = None,
        composite_method_node: "CompositeMethodNode | None" = None,
    ):
        """
        Initializes a new `ControlFlow` instance.

        :param nodes: A list of control flow nodes in the control flow graph.
        :param composite_method_node: The composite method node that owns this control flow graph.
        """
        self._nodes = nodes if nodes is not None else []
        self._composite_method_node = composite_method_node

        # Set parent CFG reference on all nodes
        for node in self._nodes:
            if node._parent_cfg is None:
                node._parent_cfg = self

    def nodes(self) -> Sequence[ControlFlowNode]:
        """
        Gets the list of control flow nodes in the control flow graph.

        :return: The list of control flow nodes in the control flow graph.
        """
        return self._nodes

    @property
    def composite_method_node(self) -> "CompositeMethodNode | None":
        """
        Get the composite method node that owns this control flow graph.

        :return: The composite method node, or None if not set.
        """
        return self._composite_method_node

    def get_data_model_id(self) -> str:
        """
        Get the data model ID of the composite method node that owns this control flow graph.

        :return: The data model ID, or empty string if not available.
        """
        if self._composite_method_node and self._composite_method_node.data_model:
            return self._composite_method_node.data_model.name
        return ""

    def get_composite_method_id(self) -> str:
        """
        Get the ID of the composite method node that owns this control flow graph.

        :return: The composite method node ID, or empty string if not available.
        """
        if self._composite_method_node:
            return self._composite_method_node.id
        return ""

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

        data_model_id = self.get_data_model_id()

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
