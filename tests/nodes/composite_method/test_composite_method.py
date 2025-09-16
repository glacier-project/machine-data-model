from typing import Callable, Any

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
from machine_data_model.nodes.variable_node import VariableNode, NumericalVariableNode
from tests import get_dummy_method_node
from tests.nodes.composite_method import get_non_blocking_cf, get_blocking_cf
from tests.test_data_model import get_template_data_model


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

        wait_node.write(new_val)
        ret = c_method.resume_execution(scope_id)

        assert len(wait_node.get_subscribers()) == 0
        for node in c_method.returns:
            assert node.read() == ret[node.name]

    @pytest.mark.parametrize(
        "variable_path",
        ["folder1/n_variable2", "folder1/n_variable1"],
    )
    def test_dynamic_read_variable_node(self, variable_path: str) -> None:
        data_model = get_template_data_model()
        dynamic_read = data_model.get_node("folder1/folder3/dynamic_read")
        node = data_model.get_node(variable_path)

        assert isinstance(node, NumericalVariableNode)
        assert isinstance(dynamic_read, CompositeMethodNode)
        args: list[Any] = [node.qualified_name]
        ret = dynamic_read(*args)

        assert ret[dynamic_read.returns[0].name] == node.read()

    @pytest.mark.parametrize(
        "variable_path",
        ["folder1/n_variable2", "folder1/n_variable1"],
    )
    def test_dynamic_write_variable_node(self, variable_path: str) -> None:
        data_model = get_template_data_model()
        dynamic_write = data_model.get_node("folder1/folder3/dynamic_write")
        node = data_model.get_node(variable_path)
        value = random.randint(100, 200)
        assert isinstance(node, NumericalVariableNode)
        assert isinstance(dynamic_write, CompositeMethodNode)

        prev_val = node.read()
        args: list[Any] = [node.qualified_name, value]
        ret = dynamic_write(*args)
        post_val = node.read()

        assert post_val != prev_val
        assert post_val == value
        assert len(ret) == 0

    @pytest.mark.parametrize(
        "method_path",
        [
            "folder1/folder2/async_method1",
        ],
    )
    def test_dynamic_call_method_node(self, method_path: str) -> None:
        data_model = get_template_data_model()
        dynamic_method = data_model.get_node("folder1/folder3/dynamic_call")
        node = data_model.get_node(method_path)
        value = 30

        assert isinstance(node, AsyncMethodNode)

        def callback(*args: list[Any], **kwargs: dict[str, Any]) -> int:
            return value

        node.callback = callback
        assert isinstance(dynamic_method, CompositeMethodNode)

        args: list[Any] = [node.qualified_name]
        ret = dynamic_method(*args)
        assert ret["n_variable10"] == value

    @pytest.mark.parametrize(
        "wait_node_path",
        ["folder1/n_variable2", "folder1/n_variable1"],
    )
    def test_dynamic_wait_node(self, wait_node_path: str) -> None:
        data_model = get_template_data_model()
        dynamic_wait = data_model.get_node("folder1/folder3/dynamic_wait")
        node = data_model.get_node(wait_node_path)

        assert isinstance(node, VariableNode)
        assert isinstance(dynamic_wait, CompositeMethodNode)

        current_value = node.read()

        def subscription_callback(
            subscriber: str, node: VariableNode, value: Any
        ) -> None:
            assert isinstance(dynamic_wait, CompositeMethodNode)
            res = dynamic_wait.resume_execution(ret[SCOPE_ID])
            assert res == {}

        node.set_subscription_callback(subscription_callback)

        args: list[Any] = [node.qualified_name, current_value]
        ret = dynamic_wait(*args)
        assert SCOPE_ID in ret
        assert not dynamic_wait.is_terminated(ret[SCOPE_ID])

        node.value += 1
        assert dynamic_wait.is_terminated(ret[SCOPE_ID])

    @pytest.mark.parametrize(
        "name_resolution_node",
        ["folder1/folder3/dynamic_node_name_resolution"],
    )
    def test_dynamic_resolution_name(self, name_resolution_node: str) -> None:
        data_model = get_template_data_model()
        dynamic_resolution = data_model.get_node(name_resolution_node)

        assert isinstance(dynamic_resolution, CompositeMethodNode)
        assert (
            dynamic_resolution(["empty_folder"], ["n_variable_empty"]).get("result")
            == 10
        ), "Failed on dynamic_resolution"
