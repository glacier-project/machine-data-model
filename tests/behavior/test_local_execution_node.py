import random
from typing import Any
import uuid

import pytest

from machine_data_model.behavior.control_flow import ControlFlow
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
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
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

    def test_nested_composite_method_call(self) -> None:
        root = FolderNode(name="root", description="Root folder")
        source_var = NumericalVariableNode(
            name="source_var",
            description="Source variable",
            value=1,
        )
        root.add_child(source_var)

        child_return = NumericalVariableNode(
            name="child_result",
            description="Child result",
            value=0,
        )
        child_method = CompositeMethodNode(
            name="child_method",
            description="Child composite method",
            returns=[child_return],
            cfg=ControlFlow(
                nodes=[
                    WaitConditionNode(
                        variable_node=source_var.qualified_name,
                        rhs=2,
                        op=WaitConditionOperator.EQ,
                    ),
                    ReadVariableNode(
                        variable_node=source_var.qualified_name,
                        store_as=child_return.name,
                    ),
                ]
            ),
        )
        root.add_child(child_method)

        parent_return = NumericalVariableNode(
            name="parent_result",
            description="Parent result",
            value=0,
        )
        target_var = NumericalVariableNode(
            name="target_var",
            description="Target variable",
            value=0,
        )
        root.add_child(target_var)

        parent_method = CompositeMethodNode(
            name="parent_method",
            description="Parent composite method",
            returns=[parent_return],
            cfg=ControlFlow(
                nodes=[
                    CallMethodNode(
                        method_node=child_method.qualified_name,
                        args=[],
                        kwargs={},
                    ),
                    WriteVariableNode(
                        variable_node=target_var.qualified_name,
                        value="${child_result}",
                    ),
                    ReadVariableNode(
                        variable_node=target_var.qualified_name,
                        store_as=parent_return.name,
                    ),
                ]
            ),
        )
        root.add_child(parent_method)

        data_model = DataModel(name="test_dm", root=root)
        assert data_model.get_node(parent_method.id) is parent_method
        assert data_model.get_node(child_method.id) is child_method

        initial_result = parent_method()
        assert "@context_id" in initial_result.return_values
        parent_context_id = initial_result.return_values["@context_id"]

        parent_context = parent_method._get_context(parent_context_id)
        pending_key = f"call_method_pending_{parent_context.get_pc()}"
        child_context_id = parent_context.get_value(pending_key)

        assert parent_context.is_active()
        assert not parent_method.is_terminated(parent_context_id)

        source_var.write(2)
        child_result = child_method.resume_execution(child_context_id)

        assert not child_result.messages
        assert parent_method.is_terminated(parent_context_id)
        assert not parent_context.is_active()
        assert parent_context.get_value("child_result") == 2
        assert parent_context.get_value(parent_return.name) == 2
        assert target_var.read() == 2

        resumed_parent = parent_method.resume_execution(parent_context_id)
        assert resumed_parent.return_values[parent_return.name] == 2
