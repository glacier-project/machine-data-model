from typing import Any

from machine_data_model.nodes.composite_method.control_flow_node import (
    ControlFlowNode,
    resolve_value,
)
from machine_data_model.nodes.composite_method.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.method_node import AsyncMethodNode


class CallMethodNode(ControlFlowNode):
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

    def execute(self, scope: ControlFlowScope) -> bool:
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
        scope.set_all_values(**res)
        return True
