"""
Visitor pattern implementation for control flow nodes.

This module defines the visitor pattern for operations on control flow nodes,
allowing operations like execution, validation, and tracing to be implemented
as separate visitor classes without modifying the node classes themselves.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from machine_data_model.behavior.control_flow_node import ControlFlowNode
    from machine_data_model.behavior.execution_context import ExecutionContext
    from machine_data_model.behavior.local_execution_node import (
        CallMethodNode,
        ReadVariableNode,
        WaitConditionNode,
        WriteVariableNode,
    )
    from machine_data_model.behavior.remote_execution_node import (
        CallRemoteMethodNode,
        ReadRemoteVariableNode,
        WaitRemoteEventNode,
        WriteRemoteVariableNode,
    )


class ControlFlowVisitor(ABC):
    """
    Abstract base class for control flow node visitors.

    Visitors implement operations that can be performed on control flow nodes
    without modifying the node classes themselves. Each visitor defines methods
    for visiting different types of nodes.
    """

    @abstractmethod
    def visit_read_variable_node(self, node: "ReadVariableNode") -> None:
        """
        Visit a ReadVariableNode.

        Args:
            node (ReadVariableNode):
                The node to visit.

        """

    @abstractmethod
    def visit_write_variable_node(self, node: "WriteVariableNode") -> None:
        """
        Visit a WriteVariableNode.

        Args:
            node (WriteVariableNode):
                The node to visit.

        """

    @abstractmethod
    def visit_call_method_node(self, node: "CallMethodNode") -> None:
        """
        Visit a CallMethodNode.

        Args:
            node (CallMethodNode):
                The node to visit.

        """

    @abstractmethod
    def visit_wait_condition_node(self, node: "WaitConditionNode") -> None:
        """
        Visit a WaitConditionNode.

        Args:
            node (WaitConditionNode):
                The node to visit.

        """

    @abstractmethod
    def visit_call_remote_method_node(self, node: "CallRemoteMethodNode") -> None:
        """
        Visit a CallRemoteMethodNode.

        Args:
            node (CallRemoteMethodNode):
                The node to visit.

        """

    @abstractmethod
    def visit_read_remote_variable_node(self, node: "ReadRemoteVariableNode") -> None:
        """
        Visit a ReadRemoteVariableNode.

        Args:
            node (ReadRemoteVariableNode):
                The node to visit.

        """

    @abstractmethod
    def visit_write_remote_variable_node(self, node: "WriteRemoteVariableNode") -> None:
        """
        Visit a WriteRemoteVariableNode.

        Args:
            node (WriteRemoteVariableNode):
                The node to visit.

        """

    @abstractmethod
    def visit_wait_remote_event_node(self, node: "WaitRemoteEventNode") -> None:
        """
        Visit a WaitRemoteEventNode.

        Args:
            node (WaitRemoteEventNode):
                The node to visit.

        """


class TracingVisitor(ControlFlowVisitor):
    """
    Visitor that traces control flow node execution.

    This visitor records tracing information for all control flow operations
    without performing the actual execution.
    """

    def __init__(self):
        pass

    def visit_read_variable_node(self, node: "ReadVariableNode") -> None:
        """Trace a ReadVariableNode."""
        print(f"Tracing: ReadVariableNode {node.node}")

    def visit_write_variable_node(self, node: "WriteVariableNode") -> None:
        """Trace a WriteVariableNode."""
        print(f"Tracing: WriteVariableNode {node.node}")

    def visit_call_method_node(self, node: "CallMethodNode") -> None:
        """Trace a CallMethodNode."""
        print(f"Tracing: CallMethodNode {node.node}")

    def visit_wait_condition_node(self, node: "WaitConditionNode") -> None:
        """Trace a WaitConditionNode."""
        print(f"Tracing: WaitConditionNode {node.node}")

    def visit_call_remote_method_node(self, node: "CallRemoteMethodNode") -> None:
        """Trace a CallRemoteMethodNode."""
        print(f"Tracing: CallRemoteMethodNode {node.node}")

    def visit_read_remote_variable_node(self, node: "ReadRemoteVariableNode") -> None:
        """Trace a ReadRemoteVariableNode."""
        print(f"Tracing: ReadRemoteVariableNode {node.node}")

    def visit_write_remote_variable_node(self, node: "WriteRemoteVariableNode") -> None:
        """Trace a WriteRemoteVariableNode."""
        print(f"Tracing: WriteRemoteVariableNode {node.node}")

    def visit_wait_remote_event_node(self, node: "WaitRemoteEventNode") -> None:
        """Trace a WaitRemoteEventNode."""
        print(f"Tracing: WaitRemoteEventNode {node.node}")


class ValidationVisitor(ControlFlowVisitor):
    """
    Visitor that validates control flow nodes.

    This visitor checks that nodes are properly configured and can be executed
    without errors.
    """

    def __init__(self, context: "ExecutionContext"):
        self.context = context
        self.errors: list[str] = []

    def visit_read_variable_node(self, node: "ReadVariableNode") -> None:
        """Validate a ReadVariableNode."""
        try:
            ref_node = node._get_ref_node(self.context)
            if ref_node is None:
                self.errors.append(
                    f"ReadVariableNode {node.node}: reference node not found"
                )
        except Exception as e:
            self.errors.append(f"ReadVariableNode {node.node}: {str(e)}")

    def visit_write_variable_node(self, node: "WriteVariableNode") -> None:
        """Validate a WriteVariableNode."""
        try:
            ref_node = node._get_ref_node(self.context)
            if ref_node is None:
                self.errors.append(
                    f"WriteVariableNode {node.node}: reference node not found"
                )
        except Exception as e:
            self.errors.append(f"WriteVariableNode {node.node}: {str(e)}")

    def visit_call_method_node(self, node: "CallMethodNode") -> None:
        """Validate a CallMethodNode."""
        try:
            ref_node = node._get_ref_node(self.context)
            if ref_node is None:
                self.errors.append(
                    f"CallMethodNode {node.node}: reference node not found"
                )
        except Exception as e:
            self.errors.append(f"CallMethodNode {node.node}: {str(e)}")

    def visit_wait_condition_node(self, node: "WaitConditionNode") -> None:
        """Validate a WaitConditionNode."""
        try:
            ref_node = node._get_ref_node(self.context)
            if ref_node is None:
                self.errors.append(
                    f"WaitConditionNode {node.node}: reference node not found"
                )
        except Exception as e:
            self.errors.append(f"WaitConditionNode {node.node}: {str(e)}")

    def visit_call_remote_method_node(self, node: "CallRemoteMethodNode") -> None:
        """Validate a CallRemoteMethodNode."""
        if not node.sender_id:
            self.errors.append(f"CallRemoteMethodNode {node.node}: sender_id not set")

    def visit_read_remote_variable_node(self, node: "ReadRemoteVariableNode") -> None:
        """Validate a ReadRemoteVariableNode."""
        if not node.sender_id:
            self.errors.append(f"ReadRemoteVariableNode {node.node}: sender_id not set")

    def visit_write_remote_variable_node(self, node: "WriteRemoteVariableNode") -> None:
        """Validate a WriteRemoteVariableNode."""
        if not node.sender_id:
            self.errors.append(
                f"WriteRemoteVariableNode {node.node}: sender_id not set"
            )

    def visit_wait_remote_event_node(self, node: "WaitRemoteEventNode") -> None:
        """Validate a WaitRemoteEventNode."""
        if not node.sender_id:
            self.errors.append(f"WaitRemoteEventNode {node.node}: sender_id not set")

    def is_valid(self) -> bool:
        """Return True if no validation errors were found."""
        return len(self.errors) == 0

    def get_errors(self) -> list[str]:
        """Return the list of validation errors."""
        return self.errors.copy()
