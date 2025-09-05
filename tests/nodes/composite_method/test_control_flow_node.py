import uuid
import random
from typing import Any

import pytest

from machine_data_model.behavior.call_method_node import CallMethodNode
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.behavior.read_variable_node import (
    ReadVariableNode,
)
from machine_data_model.behavior.wait_condition_node import (
    WaitConditionOperator,
    WaitConditionNode,
    get_condition_operator,
)
from machine_data_model.behavior.write_variable_node import (
    WriteVariableNode,
)
from machine_data_model.nodes.method_node import MethodNode, AsyncMethodNode
from machine_data_model.nodes.variable_node import VariableNode, StringVariableNode
from tests import (
    get_dummy_method_node,
    get_default_kwargs,
    get_random_numerical_node,
    get_random_boolean_node,
    get_random_string_node,
)


@pytest.mark.parametrize(
    "scope",
    [
        ControlFlowScope(str(uuid.uuid4())),
    ],
)
class TestControlFlowNode:
    @pytest.mark.parametrize(
        "method_node",
        [
            get_dummy_method_node(method_types=[AsyncMethodNode]),
        ],
    )
    def test_call_method_node(
        self, scope: ControlFlowScope, method_node: MethodNode
    ) -> None:
        kwargs = get_default_kwargs(method_node)
        c_method_node = CallMethodNode(
            method_node=method_node.qualified_name, args=[], kwargs=kwargs
        )
        c_method_node.set_ref_node(method_node)

        ret = c_method_node.execute(scope)

        assert c_method_node.node == method_node.qualified_name
        assert ret
        for param in method_node.returns:
            assert param.read() == scope.get_value(param.name)

    @pytest.mark.parametrize(
        "variable_node",
        [
            get_random_numerical_node(),
            get_random_boolean_node(),
            get_random_string_node(),
        ],
    )
    def test_read_variable_node(
        self, scope: ControlFlowScope, variable_node: VariableNode
    ) -> None:
        r_variable_node = ReadVariableNode(
            variable_node.qualified_name, variable_node.name
        )
        r_variable_node.set_ref_node(variable_node)

        ret = r_variable_node.execute(scope)

        assert r_variable_node.node == variable_node.qualified_name
        assert r_variable_node.store_as == variable_node.name
        assert ret
        assert variable_node.read() == scope.get_value(variable_node.name)

    @pytest.mark.parametrize(
        "variable_node,value",
        [
            [get_random_numerical_node(), random.randint(0, 100)],
            [get_random_boolean_node(), random.choice([True, False])],
            [get_random_string_node(), random.choice(["a", "b", "c"])],
        ],
    )
    def test_write_variable_node(
        self, scope: ControlFlowScope, variable_node: VariableNode, value: Any
    ) -> None:
        w_variable_node = WriteVariableNode(variable_node.qualified_name, value)
        w_variable_node.set_ref_node(variable_node)

        ret = w_variable_node.execute(scope)

        assert w_variable_node.node == variable_node.qualified_name
        assert ret
        assert variable_node.read() == value

    @pytest.mark.parametrize(
        "variable_node,rhs",
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
        self, scope: ControlFlowScope, variable_node: VariableNode, rhs: Any, op: str
    ) -> None:
        w_variable_node = WaitConditionNode(
            variable_node.qualified_name, rhs, get_condition_operator(op)
        )
        w_variable_node.set_ref_node(variable_node)

        ret = w_variable_node.execute(scope)
        if isinstance(variable_node, StringVariableNode):
            comparison_result = eval(f'"{variable_node.read()}"' + op + f'"{rhs}"')
        else:
            comparison_result = eval(f"{variable_node.read()}" + op + f"{rhs}")

        assert w_variable_node.node == variable_node.qualified_name
        print("Comparison result: ", f'"{variable_node.read()}"' + op + f'"{rhs}"')
        assert ret == comparison_result
