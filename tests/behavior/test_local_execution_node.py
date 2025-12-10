import random
from typing import Any
import uuid

import pytest

from machine_data_model.behavior.execution_context import (
    ExecutionContext,
)
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
    WaitConditionNode,
    WaitConditionOperator,
    WriteVariableNode,
    get_condition_operator,
)
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import (
    StringVariableNode,
    VariableNode,
)
from tests import (
    get_default_kwargs,
    get_dummy_method_node,
    get_random_boolean_node,
    get_random_numerical_node,
    get_random_string_node,
)


class TestLocalExecutionNode:
    @pytest.mark.parametrize(
        "method_node",
        [
            get_dummy_method_node(method_types=[AsyncMethodNode]),
        ],
    )
    def test_call_method_node(self, method_node: MethodNode) -> None:
        context = ExecutionContext(str(uuid.uuid4()))
        kwargs = get_default_kwargs(method_node)
        c_method_node = CallMethodNode(
            method_node=method_node.qualified_name, args=[], kwargs=kwargs
        )
        c_method_node.set_ref_node(method_node)

        ret = c_method_node.execute(context)

        assert c_method_node.node == method_node.qualified_name
        assert ret
        for param in method_node.returns:
            assert param.read() == context.get_value(param.name)

    @pytest.mark.parametrize(
        "variable_node",
        [
            get_random_numerical_node(),
            get_random_boolean_node(),
            get_random_string_node(),
        ],
    )
    def test_read_variable_node(self, variable_node: VariableNode) -> None:
        context = ExecutionContext(str(uuid.uuid4()))
        r_variable_node = ReadVariableNode(
            variable_node.qualified_name, variable_node.name
        )
        r_variable_node.set_ref_node(variable_node)

        ret = r_variable_node.execute(context)

        assert r_variable_node.node == variable_node.qualified_name
        assert r_variable_node.store_as == variable_node.name
        assert ret.success
        assert len(ret.messages) == 0
        assert variable_node.read() == context.get_value(variable_node.name)

    @pytest.mark.parametrize(
        "variable_node, value",
        [
            [get_random_numerical_node(), random.randint(0, 100)],
            [get_random_boolean_node(), random.choice([True, False])],
            [get_random_string_node(), random.choice(["a", "b", "c"])],
        ],
    )
    def test_write_variable_node(
        self, variable_node: VariableNode, value: Any
    ) -> None:
        context = ExecutionContext(str(uuid.uuid4()))
        w_variable_node = WriteVariableNode(variable_node.qualified_name, value)
        w_variable_node.set_ref_node(variable_node)

        ret = w_variable_node.execute(context)

        assert w_variable_node.node == variable_node.qualified_name
        assert ret.success
        assert len(ret.messages) == 0
        assert variable_node.read() == value

    @pytest.mark.parametrize(
        "variable_node, rhs",
        [
            [get_random_numerical_node(), random.randint(0, 100)],
            [get_random_boolean_node(), random.choice([True, False])],
            [get_random_string_node(), random.choice(["a", "b", "c"])],
        ],
    )
    @pytest.mark.parametrize(
        "op",
        [enum_op.value for enum_op in WaitConditionOperator],
    )
    def test_wait_condition_node(
        self, variable_node: VariableNode, rhs: Any, op: str
    ) -> None:
        context = ExecutionContext(str(uuid.uuid4()))
        w_variable_node = WaitConditionNode(
            variable_node.qualified_name, rhs, get_condition_operator(op)
        )
        w_variable_node.set_ref_node(variable_node)

        ret = w_variable_node.execute(context)
        if isinstance(variable_node, StringVariableNode):
            comparison_result = eval(
                f'"{variable_node.read()}"' + op + f'"{rhs}"'
            )
        else:
            comparison_result = eval(f"{variable_node.read()}" + op + f"{rhs}")

        assert w_variable_node.node == variable_node.qualified_name
        assert ret.success == comparison_result
        assert len(ret.messages) == 0
