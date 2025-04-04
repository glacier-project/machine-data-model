from typing import Callable

import pytest
import random

from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
    SCOPE_ID,
)
from machine_data_model.nodes.composite_method.control_flow import ControlFlow
from machine_data_model.nodes.composite_method.wait_condition_node import (
    WaitConditionNode,
)
from machine_data_model.nodes.method_node import AsyncMethodNode
from machine_data_model.nodes.variable_node import VariableNode
from tests import get_dummy_method_node
from tests.nodes.composite_method import get_non_blocking_cf, get_blocking_cf


def get_composite_method(
    method_nodes: list[AsyncMethodNode],
    cfg_ctor: Callable[[list[AsyncMethodNode]], ControlFlow],
) -> CompositeMethodNode:
    c_method = get_dummy_method_node(method_types=[CompositeMethodNode])
    a_method = get_dummy_method_node(
        method_types=[AsyncMethodNode], returns=c_method.returns
    )
    assert isinstance(c_method, CompositeMethodNode)
    assert isinstance(a_method, AsyncMethodNode)
    method_nodes.append(a_method)
    c_method.cfg = cfg_ctor(method_nodes)
    return c_method


def get_wait_var_node(cfg: ControlFlow) -> VariableNode:
    for node in cfg.nodes():
        if isinstance(node, WaitConditionNode):
            var_node = node.get_ref_node()
            assert isinstance(var_node, VariableNode)
            return var_node
    raise ValueError("No WaitConditionNode found in ControlFlow")


class TestCompositeMethod:
    @pytest.mark.parametrize(
        "method_nodes",
        [
            [get_dummy_method_node(method_types=[AsyncMethodNode]) for _ in range(3)],
        ],
    )
    def test_non_blocking_composite_method(
        self, method_nodes: list[AsyncMethodNode]
    ) -> None:
        c_method = get_composite_method(method_nodes, get_non_blocking_cf)

        ret = c_method()

        for node in c_method.returns:
            assert node.read() == ret[node.name]

    @pytest.mark.parametrize(
        "method_nodes",
        [
            [get_dummy_method_node(method_types=[AsyncMethodNode]) for _ in range(3)],
        ],
    )
    def test_blocking_composite_method(
        self, method_nodes: list[AsyncMethodNode]
    ) -> None:
        c_method = get_composite_method(method_nodes, get_blocking_cf)
        wait_node = get_wait_var_node(c_method.cfg)
        node_val = wait_node.read()
        ret = c_method()
        scope_id = ret[SCOPE_ID]

        assert len(wait_node.get_subscribers()) > 0

        new_val = 0
        while node_val == new_val:
            new_val = random.randint(0, 100)

        wait_node.update(new_val)
        ret = c_method.resume_execution(scope_id)

        assert len(wait_node.get_subscribers()) == 0
        for node in c_method.returns:
            assert node.read() == ret[node.name]
