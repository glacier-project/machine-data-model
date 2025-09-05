from typing import Any
from abc import ABC, abstractmethod
from collections.abc import Callable
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage


def is_variable(value: Any) -> bool:
    """
    Check if the value is a variable that must be resolved in the scope.
    A variable is considered to be a string starting with '$'.

    :param value: The value to check.
    :return: True if the value is a variable, otherwise False.
    """
    return isinstance(value, str) and value.startswith("$")


def resolve_value(value: Any, scope: ControlFlowScope) -> Any:
    """
    Resolve the value of a variable in the scope. If the value is a string starting with '$',
    it is considered a variable and the value is resolved from the scope. Otherwise, the value
    is returned as is.
    """
    if is_variable(value):
        return scope.get_value(value[1:])
    return value


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
    flow scope.

    :ivar node: The identifier of a node in the machine data model.
    :ivar _successors: A list of control flow nodes that are successors of the current node. (Not used yet)
    """

    def __init__(self, node: str, successors: list["ControlFlowNode"] | None = None):
        """
        Initialize a new ControlFlowNode instance.

        :param node: The identifier of a node in the machine data model.
        :param successors: A list of control flow nodes that are successors of the current node.
        """
        self.node = node
        self._successors = [] if successors is None else successors

    @abstractmethod
    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        """
        Execute the control flow node in the context of the specified scope.

        :param scope: The scope of the control flow graph.
        :return: An ExecutionNodeResult object representing the result of the execution.
        """
        pass


class LocalExecutionNode(ControlFlowNode):
    """
    Abstract base class representing a control flow action node in the control flow graph. A control flow action node is a basic unit of the control flow graph that can be executed locally in the context of a control flow scope.

    :ivar node: The identifier of a local node in the machine data model.
    :ivar _ref_node: The reference to the node in the machine data model.
    :ivar get_data_model_node: A callable that takes a node identifier and returns the corresponding node in the machine data model.
    """

    def __init__(self, node: str, successors: list["ControlFlowNode"] | None = None):
        """
        Initialize a new CFActionNode instance.

        :param node: The identifier of a local node in the machine data model.
        :param successors: A list of control flow nodes that are successors of the current node.
        """
        super().__init__(node, successors)

        self.node = node
        self._ref_node: DataModelNode | None = None
        self.get_data_model_node: Callable[[str], DataModelNode | None] | None = None

    def get_successors(self) -> list["ControlFlowNode"]:
        """
        Gets the list of control flow nodes that are successors of the current node.

        :return: The list of control flow nodes that are successors of the current node.
        """
        return self._successors

    def is_node_static(self) -> bool:
        """
        Check if the node is static. This is used to determine if the reference node
        can be resolved at creation time or if it needs to be resolved at execution time.

        :return: True if the node is static, otherwise False.
        """
        return self.node is not None and not is_variable(self.node)

    def set_ref_node(self, ref_node: DataModelNode) -> None:
        """
        Set the reference to the node in the machine data model.

        :param ref_node: The reference to the node in the machine data model.
        """
        assert ref_node.name == self.node.split("/")[-1]
        self._ref_node = ref_node

    def get_ref_node(self) -> DataModelNode | None:
        """
        Get the reference to the node in the machine data model.

        :return: The reference to the node in the machine data model.
        """
        return self._ref_node

    def _get_ref_node(self, scope: ControlFlowScope) -> DataModelNode | None:
        """
        Get the node referenced by the current node. If the node is static, it returns the
        reference node. Otherwise, it resolves the value of the node in the scope and
        retrieves the reference node from the machine data model.

        :param scope: The scope of the control flow graph.
        :return: The node referenced by the current node.
        """

        if self.is_node_static():
            return self._ref_node
        node_path = resolve_value(self.node, scope)
        assert self.get_data_model_node is not None
        return self.get_data_model_node(node_path)
