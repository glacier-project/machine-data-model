from typing import Any
from abc import ABC, abstractmethod

from machine_data_model.nodes.composite_method.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.data_model_node import DataModelNode


def resolve_value(value: Any, scope: ControlFlowScope) -> Any:
    """
    Resolve the value of a variable in the scope. If the value is a string starting with '$',
    it is considered a variable and the value is resolved from the scope. Otherwise, the value
    is returned as is.
    """
    if isinstance(value, str) and value.startswith("$"):
        return scope.get_value(value[1:])
    return value


class ControlFlowNode(ABC):
    """
    Abstract base class representing a node in the control flow graph. A control flow node
    is a basic unit of the control flow graph that can be executed in the context of a control
    flow scope.

    :ivar node: The identifier of a node in the machine data model.
    :ivar _ref_node: The reference to the node in the machine data model.
    :ivar _successors: A list of control flow nodes that are successors of the current node. (Not used yet)
    """

    def __init__(self, node: str, successors: list["ControlFlowNode"] | None = None):
        """
        Initialize a new ControlFlowNode instance.

        :param node: The identifier of a node in the machine data model.
        :param successors: A list of control flow nodes that are successors of the current node.
        """
        self.node = node
        self._ref_node: DataModelNode | None = None
        self._successors = [] if successors is None else successors

    def get_successors(self) -> list["ControlFlowNode"]:
        """
        Gets the list of control flow nodes that are successors of the current node.

        :return: The list of control flow nodes that are successors of the current node.
        """
        return self._successors

    def set_ref_node(self, ref_node: DataModelNode) -> None:
        """
        Set the reference to the node in the machine data model.

        :param ref_node: The reference to the node in the machine data model.
        """
        assert ref_node.name == self.node.split("/")[-1]
        self._ref_node = ref_node

    @abstractmethod
    def execute(self, scope: ControlFlowScope) -> bool:
        """
        Execute the control flow node in the context of the specified scope.

        :param scope: The scope of the control flow graph.
        :return: True if the execution is successful, otherwise False.
        """
        pass
