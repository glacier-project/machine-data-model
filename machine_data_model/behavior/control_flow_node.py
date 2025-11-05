from abc import ABC, abstractmethod
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage


# def is_variable(value: Any) -> bool:
#     """
#     Check if the value is a variable that must be resolved in the scope.
#     A variable is considered to be a string starting with '$'.

#     :param value: The value to check.
#     :return: True if the value is a variable, otherwise False.
#     """
#     return isinstance(value, str) and value.startswith("$")


# def is_template_variable(value: Any) -> bool:
#     """
#     Check if the value is a template variable that must be resolved in the scope.
#     A template variable is considered to be a string starting with '${' and ending with '}'.

#     :param value: The value to check.
#     :return: True if the value is a template variable, otherwise False.
#     """
#     return isinstance(value, str) and "${" in value and "}" in value


# def resolve_value(value: Any, scope: ControlFlowScope) -> Any:
#     """
#     Resolve the value of a variable in the scope. If the value is a string starting with '$',
#     it is considered a variable and the value is resolved from the scope. Otherwise, the value
#     is returned as is.
#     """
#     if is_variable(value):
#         return scope.get_value(value[1:])
#     return value


class ExecutionNodeResult:
    """
    Represents the result of executing a control flow node.

    Attributes:
        success (bool): True if the execution was successful, otherwise False.
        messages (list[FrostMessage] | None): A list of Frost messages to be sent, if any.
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
    Abstract base class for a node in the control flow graph.

    A control flow node is a basic unit that can be executed in the context of a scope.

    Attributes:
        node (str): The identifier of a node in the machine data model.
        _successors (list["ControlFlowNode"]): A list of successor nodes (not used yet).
    """

    def __init__(self, node: str, successors: list["ControlFlowNode"] | None = None):
        """
        Initializes a new ControlFlowNode instance.

        Args:
            node (str): The identifier of a node in the machine data model.
            successors (list["ControlFlowNode"] | None): A list of successor nodes.
        """
        self.node = node
        self._successors = [] if successors is None else successors

    @abstractmethod
    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        """
        Executes the control flow node in the context of the specified scope.

        Args:
            scope (ControlFlowScope): The scope of the control flow graph.

        Returns:
            ExecutionNodeResult: The result of the execution.
        """
        pass

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, ControlFlowNode):
            return False

        return self.node == other.node
