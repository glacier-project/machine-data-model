import pytest

from machine_data_model.nodes.method_node import MethodNode
from tests import NUM_TESTS, gen_random_string, get_random_numerical_node


@pytest.mark.parametrize(
    "method_name, method_description",
    [(gen_random_string(10), gen_random_string(20)) for _ in range(3)],
)
class TestMethodNode:

    def test_method_node_creation(self, method_name, method_description):
        method = MethodNode(name=method_name, description=method_description)

        assert method.name == method_name
        assert method.description == method_description
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
        self, method_name, method_description, parameters, returns
    ):
        def callback(var_1, var_2):
            return var_1 + var_2

        method = MethodNode(
            name=method_name,
            description=method_description,
            callback=callback,
            parameters=parameters,
            returns=returns,
        )

        result = method()

        assert method.name == method_name
        assert method.description == method_description
        assert result[returns[0].name] == parameters[0].read() + parameters[1].read()

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
        self, method_name, method_description, parameters, returns
    ):
        method = MethodNode(name=method_name, description=method_description)
        for param in parameters:
            method.add_parameter(param)
        for ret in returns:
            method.add_return_value(ret)

        def callback(var_1, var_2):
            return var_1 + var_2

        method._callback = callback

        result = method()

        assert method.name == method_name
        assert method.description == method_description
        assert result[returns[0].name] == parameters[0].read() + parameters[1].read()
