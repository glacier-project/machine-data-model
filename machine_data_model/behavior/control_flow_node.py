from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage

if TYPE_CHECKING:
    from machine_data_model.behavior.control_flow import ControlFlow


class ExecutionNodeResult:
    """
    Represents the result of executing a control flow node.
    :ivar success: True if the execution was successful, otherwise False.
    :ivar messages: A list of FrostMessage to be sent, if any.
    """

    def __init__(self, success: bool, messages: list[FrostMessage] | None = None):
        self.success = success
        self.messages = messages if messages is not None else []


def execution_success(
    messages: list[FrostMessage] | None = None,
) -> ExecutionNodeResult:
    """Create a successful ExecutionNodeResult."""
    return ExecutionNodeResult(True, messages)


def execution_failure(
    messages: list[FrostMessage] | None = None,
) -> ExecutionNodeResult:
    """Create a failed ExecutionNodeResult."""
    return ExecutionNodeResult(False, messages)


class ControlFlowNode(ABC):
    """
    Abstract base class representing a node in the control flow graph. A control flow node
    is a basic unit of the control flow graph that can be executed in the context of a control
    flow execution context.

    :ivar node: The identifier of a node in the machine data model.
    :ivar _successors: A list of control flow nodes that are successors of the current node. (Not used yet)
    :ivar _parent_cfg: The parent control flow graph that contains this node.
    """

    def __init__(
        self,
        node: str,
        successors: list["ControlFlowNode"] | None = None,
        parent_cfg: "ControlFlow | None" = None,
    ):
        """
        Initialize a new ControlFlowNode instance.

        :param node: The identifier of a node in the machine data model.
        :param successors: A list of control flow nodes that are successors of the current node.
        :param parent_cfg: The parent control flow graph that contains this node.
        """
        self.node = node
        self._successors = [] if successors is None else successors
        self._parent_cfg = parent_cfg

    @property
    def parent_cfg(self) -> "ControlFlow | None":
        """
        Get the parent control flow graph that contains this node.

        :return: The parent control flow graph, or None if not set.
        """
        return self._parent_cfg

    def get_data_model_id(self) -> str:
        """
        Get the data model ID of the composite method that owns the control flow graph.

        :return: The data model ID, or empty string if not available.
        """
        if self._parent_cfg:
            return self._parent_cfg.get_data_model_id()
        return ""

    def get_composite_method_id(self) -> str:
        """
        Get the ID of the composite method that owns the control flow graph.

        :return: The composite method ID, or the node's own identifier if not available.
        """
        if self._parent_cfg:
            return self._parent_cfg.get_composite_method_id()
        return self.node

    @abstractmethod
    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """
        Execute the control flow node in the context of the specified execution
        context.

        :param context: The execution context of the control flow graph.
        :return: An ExecutionNodeResult object representing the result of the
            execution.
        """
        pass

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, ControlFlowNode):
            return False

        return self.node == other.node
