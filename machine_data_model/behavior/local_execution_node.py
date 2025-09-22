from typing import Callable, Any
from enum import Enum

from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    is_variable,
    resolve_value,
    ExecutionNodeResult,
    execution_success,
    execution_failure,
    is_template_variable,
)
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.nodes.method_node import AsyncMethodNode
from machine_data_model.tracing import trace_wait_start, trace_wait_end


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
        return (
            self.node is not None
            and not is_variable(self.node)
            and not is_template_variable(self.node)
        )

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
        if self.is_node_static() and self._ref_node is not None:
            return self._ref_node
        node_path = ""
        if is_variable(self.node):
            node_path = resolve_value(self.node, scope)
            assert node_path != "", f"Invalid template variable: {self.node}"
        else:
            node_path = self.node

        assert self.get_data_model_node is not None
        x = self.get_data_model_node(node_path)
        assert x is not None, f"Invalid node path: {node_path}"
        return x

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, LocalExecutionNode):
            return False

        return super().__eq__(other)


class ReadVariableNode(LocalExecutionNode):
    """
    Represents the read operation of a variable in the machine data model.
    When executed, it reads the value of the variable and stores it in the scope.

    :ivar store_as: The name of the variable used to store the value in the scope.
    """

    def __init__(
        self,
        variable_node: str,
        store_as: str = "",
        successors: list["ControlFlowNode"] | None = None,
    ):
        """
        Initialize a new ReadVariableNode instance.

        :param variable_node: The identifier of the variable node in the machine data model.
        :param store_as: The name of the variable used to store the value in the scope. If not specified, the value is stored with the name of the variable node.
        """
        super().__init__(variable_node, successors)
        self.store_as = store_as

    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        """
        Execute the read operation of the variable in the machine data model.

        :param scope: The scope of the control flow graph.
        :return: Returns always True.
        """
        ref_variable = self._get_ref_node(scope)
        assert isinstance(
            ref_variable, VariableNode
        ), f"Node {ref_variable} is not a VariableNode"

        value = ref_variable.read()
        name = self.store_as if self.store_as else ref_variable.name
        scope.set_value(name, value)
        return execution_success()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, ReadVariableNode):
            return False

        return super().__eq__(other) and self.store_as == other.store_as


class WriteVariableNode(LocalExecutionNode):
    """
    Represents the write operation of a variable in the machine data model.
    When executed, it writes the value to the variable in the machine data model.

    :ivar value: The value to write to the variable.
    """

    def __init__(
        self,
        variable_node: str,
        value: Any,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """
        Initialize a new WriteVariableNode instance.

        :param variable_node: The identifier of the variable node in the machine data model.
        :param value: The value to write to the variable. It can be a constant value or reference to a variable in the scope.
        """
        super().__init__(variable_node, successors)
        self._value = value

    @property
    def value(self) -> Any:
        """
        Get the value to write to the variable.

        :return: The value to write to the variable.
        """
        return self._value

    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        """
        Execute the write operation of the variable in the machine data model.

        :param scope: The scope of the control flow graph.
        :return: Returns always True.
        """
        ref_variable = self._get_ref_node(scope)
        assert isinstance(ref_variable, VariableNode)

        value = resolve_value(self._value, scope)
        ref_variable.write(value)
        return execution_success()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, WriteVariableNode):
            return False

        return super().__eq__(other) and self.value == other.value


class CallMethodNode(LocalExecutionNode):
    """
    Represents the call operation of a method in the machine data model. When executed,
    it calls the method with the specified arguments and stores the return values in the scope.

    :ivar _args: The list of positional arguments to pass to the method.
    :ivar _kwargs: The dictionary of keyword arguments to pass to the method.
    """

    def __init__(
        self,
        method_node: str,
        args: list[Any],
        kwargs: dict[str, Any],
        successors: list["ControlFlowNode"] | None = None,
    ):
        super().__init__(method_node, successors)
        self._args = args
        self._kwargs = kwargs

    @property
    def args(self) -> list[Any]:
        """
        Get the list of positional arguments to pass to the method.

        :return: The list of positional arguments to pass to the method.
        """
        return self._args

    @property
    def kwargs(self) -> dict[str, Any]:
        """
        Get the dictionary of keyword arguments to pass to the method.

        :return: The dictionary of keyword arguments to pass to the method.
        """
        return self._kwargs

    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        """
        Execute the call operation of the method in the machine data model.

        :param scope: The scope of the control flow graph.
        :return: Returns always True.
        """
        ref_method = self._get_ref_node(scope)
        assert isinstance(ref_method, AsyncMethodNode)

        # resolve variables in the scope
        args = [resolve_value(arg, scope) for arg in self._args]
        kwargs = {k: resolve_value(v, scope) for k, v in self._kwargs.items()}
        res = ref_method(*args, **kwargs)
        scope.set_all_values(**res.return_values)
        return execution_success()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, CallMethodNode):
            return False

        return (
            super().__eq__(other)
            and self.args == other.args
            and self.kwargs == other.kwargs
        )


class WaitConditionOperator(str, Enum):
    """
    Enumeration of wait condition operators.
    """

    EQ = "=="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="


def get_condition_operator(op: str) -> WaitConditionOperator:
    """
    Utility function to get the wait condition operator from a string representation.
    """
    for enum_op in WaitConditionOperator:
        if enum_op.value == op:
            return enum_op
    raise ValueError(f"Invalid operator: {op}")


class WaitConditionNode(LocalExecutionNode):
    """
    Represents a wait condition in the control flow graph. When executed, it compares the value
    of a variable with a constant value or another variable.
    It returns immediately if the condition is met, otherwise it subscribes to the variable
    and waits for the value to change.
    """

    def __init__(
        self,
        variable_node: str,
        rhs: Any,
        op: WaitConditionOperator,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """
        Initialize a new WaitConditionNode instance.

        :param variable_node: The identifier of the variable node in the machine data model.
        :param rhs: The right-hand side of the comparison. It can be a constant value or reference to a variable in the scope.
        :param op: The comparison operator.
        """
        super().__init__(variable_node, successors)
        self._rhs = rhs
        self._op = op

    @property
    def rhs(self) -> Any:
        """
        Get the right-hand side of the comparison.

        :return: The right-hand side of the comparison.
        """
        return self._rhs

    @property
    def op(self) -> WaitConditionOperator:
        """
        Get the comparison operator.

        :return: The comparison operator.
        """
        return self._op

    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        """
        Execute the wait condition in the control flow graph. If the condition is met, it returns
        immediately. Otherwise, it subscribes to the variable and returns False.

        :param scope: The scope of the control flow graph.
        :return: True if the condition is met, otherwise False.
        """
        ref_variable = self._get_ref_node(scope)
        assert isinstance(ref_variable, VariableNode)

        rhs = resolve_value(self._rhs, scope)
        lhs = ref_variable.read()
        if self._op == WaitConditionOperator.EQ:
            res = lhs == rhs
        elif self._op == WaitConditionOperator.NE:
            res = lhs != rhs
        elif self._op == WaitConditionOperator.LT:
            res = lhs < rhs
        elif self._op == WaitConditionOperator.GT:
            res = lhs > rhs
        elif self._op == WaitConditionOperator.LE:
            res = lhs <= rhs
        elif self._op == WaitConditionOperator.GE:
            res = lhs >= rhs
        else:
            raise ValueError(f"Invalid operator: {self._op}")

        wait_key = f"wait_start_{self.node}_{scope.id()}"

        if not res:
            # Condition not met - start waiting
            if scope.id() not in ref_variable.get_subscribers():
                # First time waiting for this condition
                start_time = trace_wait_start(
                    self.node,
                    f"{lhs} {self._op.value} {rhs}",
                    rhs,
                    source=scope.id()
                )
                scope.set_value(wait_key, start_time)
                ref_variable.subscribe(scope.id())
            return execution_failure()

        # Condition met - stop waiting
        ref_variable.unsubscribe(scope.id())
        if wait_key in scope.locals():
            # We were waiting, now we're done
            start_time = scope.get_value(wait_key)
            trace_wait_end(self.node, start_time, source=scope.id())
            # Clean up the wait start time
            del scope.locals()[wait_key]
        return execution_success()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, WaitConditionNode):
            return False

        return super().__eq__(other) and self.op == other.op and self.rhs == other.rhs
