import pytest

from machine_data_model.behavior.execution_context import (
    ExecutionContext,
)
from machine_data_model.nodes.method_node import AsyncMethodNode
from tests import get_dummy_method_node
from tests.nodes.composite_method import get_non_blocking_cf, get_blocking_cf


class TestControlFlow:
    @pytest.mark.parametrize(
        "method_nodes",
        [
            [get_dummy_method_node(method_types=[AsyncMethodNode]) for _ in range(3)],
        ],
    )
    def test_non_blocking_control_flow(
        self, method_nodes: list[AsyncMethodNode]
    ) -> None:
        context = ExecutionContext(context_id="test_context")
        cf = get_non_blocking_cf(method_nodes)

        cf.execute(context)

        assert not context.is_active()
        assert context.get_pc() == len(cf.nodes())
        for node in method_nodes:
            for param in node.returns:
                assert param.read() == context.get_value(param.name)

    @pytest.mark.parametrize(
        "method_nodes",
        [
            [get_dummy_method_node(method_types=[AsyncMethodNode]) for _ in range(3)],
        ],
    )
    def test_blocking_control_flow(self, method_nodes: list[AsyncMethodNode]) -> None:
        context = ExecutionContext(context_id="test_context")
        cf = get_blocking_cf(method_nodes)

        cf.execute(context)

        assert context.is_active()
        assert context.get_pc() < len(cf.nodes())
        for node in method_nodes:
            for param in node.returns:
                assert param.read() == context.get_value(param.name)
