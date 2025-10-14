import random

import pytest

from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import VariableNode
from tests import NUM_TESTS, gen_random_string, get_random_numerical_node


@pytest.mark.parametrize(
    "method_name, method_description, async_method",
    [
        (gen_random_string(10), gen_random_string(20), random.choice([True, False]))
        for _ in range(3)
    ],
)
class TestMethodNode:
    def test_method_node_creation(
        self, method_name: str, method_description: str, async_method: bool
    ) -> None:
        ctor = MethodNode if not async_method else AsyncMethodNode
        method = ctor(name=method_name, description=method_description)

        assert method.name == method_name
        assert method.description == method_description
        assert method.is_async() == async_method
        assert len(method.parameters) == 0
        assert len(method.returns) == 0

    @pytest.mark.parametrize(
        "parameters, returns",
        [
            (
                [
                    get_random_numerical_node(var_name="var_1"),
                    get_random_numerical_node(var_name="var_2"),
                ],
                [get_random_numerical_node()],
            )
            for _ in (range(NUM_TESTS),)
        ],
    )
    def test_method_node_call(
        self,
        method_name: str,
        method_description: str,
        async_method: bool,
        parameters: list[VariableNode],
        returns: list[VariableNode],
    ) -> None:
        def callback(var_1: float, var_2: float) -> float:
            return var_1 + var_2

        ctor = MethodNode if not async_method else AsyncMethodNode
        method = ctor(
            name=method_name,
            description=method_description,
            callback=callback,
            parameters=parameters,
            returns=returns,
        )

        result = method()

        assert result.messages is None
        assert method.name == method_name
        assert method.description == method_description
        assert method.is_async() == async_method
        assert (
            result.return_values[returns[0].name]
            == parameters[0].read() + parameters[1].read()
        )

    @pytest.mark.parametrize(
        "parameters, returns",
        [
            (
                [
                    get_random_numerical_node(var_name="var_1"),
                    get_random_numerical_node(var_name="var_2"),
                ],
                [get_random_numerical_node()],
            )
            for _ in (range(NUM_TESTS),)
        ],
    )
    def test_method_node_call_post_init(
        self,
        method_name: str,
        method_description: str,
        async_method: bool,
        parameters: list[VariableNode],
        returns: list[VariableNode],
    ) -> None:
        ctor = MethodNode if not async_method else AsyncMethodNode
        method = ctor(name=method_name, description=method_description)
        for param in parameters:
            method.add_parameter(param)
        for ret in returns:
            method.add_return_value(ret)

        def callback(var_1: float, var_2: float) -> float:
            return var_1 + var_2

        method._callback = callback

        result = method()

        assert result.messages is None
        assert method.name == method_name
        assert method.description == method_description
        assert method.is_async() == async_method
        assert (
            result.return_values[returns[0].name]
            == parameters[0].read() + parameters[1].read()
        )
