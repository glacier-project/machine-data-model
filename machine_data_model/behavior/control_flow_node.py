"""
Control flow node definitions and execution results.

This module defines the abstract base class for control flow nodes and the
result structure for node executions in the machine data model.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage

if TYPE_CHECKING:
    from machine_data_model.behavior.control_flow import ControlFlow


class ExecutionNodeResult:
    """
    Represents the result of executing a control flow node.

    Attributes:
        success (bool):
            Indicates whether the execution was successful.
        messages (list[FrostMessage]):
            A list of messages generated during execution.

    """

    success: bool
    messages: list[FrostMessage]

    def __init__(self, success: bool, messages: list[FrostMessage] | None = None):
        """
        Initialize an ExecutionNodeResult instance.

        Args:
            success (bool):
                Indicates whether the execution was successful.
            messages (list[FrostMessage] | None):
                A list of messages generated during execution, or None.

        """
        self.success = success
        self.messages = messages if messages is not None else []


def execution_success(
    messages: list[FrostMessage] | None = None,
) -> ExecutionNodeResult:
    """
    Create a successful ExecutionNodeResult.

    Args:
        messages (list[FrostMessage] | None):
            A list of messages generated during execution, or None.

    Returns:
        ExecutionNodeResult:
            An ExecutionNodeResult with success set to True.

    """
    return ExecutionNodeResult(True, messages)


def execution_failure(
    messages: list[FrostMessage] | None = None,
) -> ExecutionNodeResult:
    """
    Create a failed ExecutionNodeResult.

    Args:
        messages (list[FrostMessage] | None):
            A list of messages generated during execution, or None.

    Returns:
        ExecutionNodeResult:
            An ExecutionNodeResult with success set to False.

    """
    return ExecutionNodeResult(False, messages)


class ControlFlowNode(ABC):
    """
    Abstract base class representing a node in the control flow graph.

    A control flow node is a basic unit of the control flow graph that can be
    executed in the context of a control flow execution context.

    Attributes:
        node (str):
            The identifier of a node in the machine data model.
        _successors (list["ControlFlowNode"]):
            A list of control flow nodes that are successors of the current
            node. (Not used yet)
        _parent_cfg ("ControlFlow | None"):
            The parent control flow graph that contains this node.

    """

    node: str
    _successors: list["ControlFlowNode"]
    _parent_cfg: "ControlFlow | None"

    def __init__(
        self,
        node: str,
        successors: list["ControlFlowNode"] | None = None,
        parent_cfg: "ControlFlow | None" = None,
    ):
        """
        Initialize a new ControlFlowNode instance.

        Args:
            node (str):
                The identifier of a node in the machine data model.
            successors (list["ControlFlowNode"] | None):
                A list of control flow nodes that are successors of the current
                node.
            parent_cfg ("ControlFlow | None"):
                The parent control flow graph that contains this node.

        """
        self.node = node
        self._successors = [] if successors is None else successors
        self._parent_cfg = parent_cfg

    @property
    def parent_cfg(self) -> "ControlFlow | None":
        """
        Get the parent control flow graph that contains this node.

        Returns:
            "ControlFlow | None":
                The parent control flow graph, or None if not set.

        """
        return self._parent_cfg

    def get_data_model_id(self) -> str:
        """
        Get the data model ID of the composite method that owns the control flow
        graph.

        Returns:
            str:
                The data model ID, or empty string if not available.

        """
        if self._parent_cfg:
            return self._parent_cfg.get_data_model_id()
        return ""

    def get_composite_method_id(self) -> str:
        """
        Get the ID of the composite method that owns the control flow graph.

        Returns:
            str:
                The composite method ID, or the node's own identifier if not
                available.

        """
        if self._parent_cfg:
            return self._parent_cfg.get_composite_method_id()
        return self.node

    @abstractmethod
    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """
        Execute the control flow node in the context of the specified execution
        context.

        Args:
            context (ExecutionContext):
                The execution context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult object representing the result of the
                execution.

        """

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, ControlFlowNode):
            return False

        return self.node == other.node
