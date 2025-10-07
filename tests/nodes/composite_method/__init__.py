from typing import Callable

from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.local_execution_node import (
    LocalExecutionNode,
)
from machine_data_model.behavior.local_execution_node import (
    WaitConditionNode,
    WaitConditionOperator,
)
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.method_node import AsyncMethodNode
from tests import get_random_numerical_node


def get_cf_nodes(
    method_nodes: list[AsyncMethodNode],
    ctor: Callable[[DataModelNode], LocalExecutionNode],
) -> list[LocalExecutionNode]:
    cf_nodes = []
    for node in method_nodes:
        cm_node = ctor(node)
        cm_node.set_ref_node(node)
        cf_nodes.append(cm_node)
    return cf_nodes


def get_cm_nodes(node: DataModelNode) -> LocalExecutionNode:
    return CallMethodNode(method_node=node.qualified_name, args=[], kwargs={})


def get_non_blocking_wait_node() -> WaitConditionNode:
    var_node = get_random_numerical_node()
    wait_node = WaitConditionNode(
        variable_node=var_node.qualified_name,
        op=WaitConditionOperator.EQ,
        rhs=var_node.read(),
    )
    wait_node.set_ref_node(var_node)
    return wait_node


def get_blocking_wait_node() -> WaitConditionNode:
    var_node = get_random_numerical_node()
    wait_node = WaitConditionNode(
        variable_node=var_node.qualified_name,
        op=WaitConditionOperator.NE,
        rhs=var_node.read(),
    )
    wait_node.set_ref_node(var_node)
    return wait_node


def get_non_blocking_cf(nodes: list[AsyncMethodNode]) -> ControlFlow:
    cf_nodes = get_cf_nodes(nodes, get_cm_nodes)
    cf = ControlFlow(nodes=cf_nodes)
    return cf


def get_blocking_cf(nodes: list[AsyncMethodNode]) -> ControlFlow:
    wait_node = get_blocking_wait_node()
    cf_nodes = get_cf_nodes(nodes, get_cm_nodes)
    cf_nodes.append(wait_node)

    cf = ControlFlow(nodes=cf_nodes)
    return cf
