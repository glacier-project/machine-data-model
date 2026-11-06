"""Control flow node definitions and execution results.

This module defines the abstract base class for control flow nodes and the
result structure for node executions in the machine data model.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.execution_error import ExecutionError
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage

if TYPE_CHECKING:
    from machine_data_model.behavior.control_flow import ControlFlow


class NodeStatus(Enum):
    """Enumeration of the outcomes of executing a control flow node.

    Attributes:
        SUCCESS:
            The node completed, the program counter advances.
        RUNNING:
            The node is not done yet (for example it waits for an event or for
            a response), the program counter stays and the node is executed
            again on resume.
        FAILURE:
            The node failed, the execution of the control flow ends in error.

    """

    SUCCESS = "success"
    RUNNING = "running"
    FAILURE = "failure"


class ExecutionNodeResult:
    """Represents the result of executing a control flow node.

    Attributes:
        status (NodeStatus):
            The outcome of the execution.
        messages (list[FrostMessage]):
            A list of messages generated during execution.
        error (ExecutionError | None):
            The reason of the failure, set if and only if the status is
            `NodeStatus.FAILURE`.

    """

    messages: list[FrostMessage]

    def __init__(
        self,
        success_or_status: bool | NodeStatus,
        messages: list[FrostMessage] | None = None,
        error: ExecutionError | None = None,
    ):
        """Initialize an ExecutionNodeResult instance.

        Args:
            success_or_status (bool | NodeStatus):
                The outcome of the execution. For backward compatibility a
                `bool` is accepted: True is `SUCCESS`, False is `RUNNING`.
            messages (list[FrostMessage] | None):
                A list of messages generated during execution, or None.
            error (ExecutionError | None):
                The reason of the failure. Required for `FAILURE`, not allowed
                otherwise.

        Raises:
            ValueError:
                If `error` is missing for a failure or given for another
                status.

        """
        if isinstance(success_or_status, NodeStatus):
            status = success_or_status
        else:
            status = (
                NodeStatus.SUCCESS if success_or_status else NodeStatus.RUNNING
            )
        if (status is NodeStatus.FAILURE) != (error is not None):
            raise ValueError(
                "an error must be given if and only if the status is FAILURE"
            )
        self._status = status
        self.messages = messages if messages is not None else []
        self._error = error

    @property
    def status(self) -> NodeStatus:
        """The outcome of the execution (read-only).

        Returns:
            NodeStatus:
                The status of the result.

        """
        return self._status

    @property
    def error(self) -> ExecutionError | None:
        """The reason of the failure (read-only).

        Returns:
            ExecutionError | None:
                The error if the status is `FAILURE`, otherwise None.

        """
        return self._error

    @property
    def success(self) -> bool:
        """Whether the node completed successfully.

        Returns:
            bool:
                True if the status is `SUCCESS`.

        """
        return self._status is NodeStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """Whether the node failed.

        Returns:
            bool:
                True if the status is `FAILURE`.

        """
        return self._status is NodeStatus.FAILURE


def execution_success(
    messages: list[FrostMessage] | None = None,
) -> ExecutionNodeResult:
    """Create a successful ExecutionNodeResult.

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
    """Create a not-done ExecutionNodeResult.

    Despite the name, this is not a failure: the node is `RUNNING` and is
    executed again on resume. Use `execution_error` to fail.

    Args:
        messages (list[FrostMessage] | None):
            A list of messages generated during execution, or None.

    Returns:
        ExecutionNodeResult:
            An ExecutionNodeResult with status `RUNNING`.

    """
    return ExecutionNodeResult(NodeStatus.RUNNING, messages)


def execution_error(
    error: ExecutionError,
    messages: list[FrostMessage] | None = None,
) -> ExecutionNodeResult:
    """Create a failed ExecutionNodeResult.

    Args:
        error (ExecutionError):
            The reason of the failure.
        messages (list[FrostMessage] | None):
            A list of messages generated during execution, or None.

    Returns:
        ExecutionNodeResult:
            An ExecutionNodeResult with status `FAILURE`.

    """
    return ExecutionNodeResult(NodeStatus.FAILURE, messages, error)


class ControlFlowNode(ABC):
    """Abstract base class representing a node in the control flow graph.

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
        """Initialize a new ControlFlowNode instance.

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
        """Get the parent control flow graph that contains this node.

        Returns:
            "ControlFlow | None":
                The parent control flow graph, or None if not set.

        """
        return self._parent_cfg

    def get_data_model_id(self) -> str:
        """Get the data model ID associated with this control flow node.

        Returns:
            str:
                The data model ID, or empty string if not available.

        """
        if self._parent_cfg:
            return self._parent_cfg.get_data_model_id()
        return ""

    def get_composite_method_id(self) -> str:
        """Get the ID of the composite method that owns the control flow graph.

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
        """Execute the control flow node in the given execution context.

        Args:
            context (ExecutionContext):
                The execution context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult object representing the result of the
                execution.

        """

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

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
