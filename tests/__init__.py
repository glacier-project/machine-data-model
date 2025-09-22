import random
import string
from collections.abc import Callable
from typing import Any, Sequence

from unitsnet_py.units.length import LengthUnits

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.method_node import MethodNode, AsyncMethodNode
from typing import TypeVar, overload
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
    VariableNode,
)

NUM_TESTS = 8
NUM_FOLDER_NODES = 3
NUM_METHOD_PARAMS = 3
NUM_METHOD_RETURNS = 2
NUM_OBJECT_PROPERTIES = 3
DEFAULT_NAME_LENGTH = 10
DEFAULT_DESCRIPTION_LENGTH = 20


def gen_random_string(length: int = 20) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def gen_random_int(min_value: int = 0, max_value: int = 1000) -> int:
    return random.randint(min_value, max_value)


def gen_random_float(min_value: float = 0.0, max_value: float = 1000.0) -> float:
    return random.uniform(min_value, max_value)


def gen_random_bool() -> bool:
    return random.choice([True, False])


def gen_random_simple_value() -> Any:
    return random.choice(
        [gen_random_string(), gen_random_int(), gen_random_float(), gen_random_bool()]
    )


def gen_random_dict(num_items: int = 3) -> dict:
    return {gen_random_string(5): gen_random_simple_value() for _ in range(num_items)}


def get_random_boolean_node(
    var_name: str | None = None, var_description: str | None = None
) -> BooleanVariableNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    return BooleanVariableNode(
        name=var_name, description=var_description, value=random.choice([True, False])
    )


def get_random_string_node(
    var_name: str | None = None, var_description: str | None = None
) -> StringVariableNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    return StringVariableNode(
        name=var_name, description=var_description, value=gen_random_string(10)
    )


def get_random_numerical_node(
    var_name: str | None = None, var_description: str | None = None
) -> NumericalVariableNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    return NumericalVariableNode(
        name=var_name,
        description=var_description,
        value=random.uniform(0, 1000),
        measure_unit=random.choice(
            [
                "LengthUnits.Meter",
                "NoneMeasureUnits.NONE",
                LengthUnits.Meter,
                NoneMeasureUnits.NONE,
            ]
        ),
    )


def get_random_object_node(
    var_name: str | None = None, var_description: str | None = None
) -> ObjectVariableNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    object_node = ObjectVariableNode(name=var_name, description=var_description)
    properties = get_random_nodes(
        NUM_OBJECT_PROPERTIES,
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node],
    )
    for prop in properties:
        assert isinstance(prop, VariableNode)
        object_node.add_property(prop)
    return object_node


def get_random_folder_node(
    var_name: str | None = None, var_description: str | None = None
) -> FolderNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    folder_node = FolderNode(name=var_name, description=var_description)
    children = [
        f()
        for f in [
            get_random_boolean_node,
            get_random_string_node,
            get_random_numerical_node,
        ]
    ]
    for child in children:
        folder_node.add_child(child)
    return folder_node


def get_default_args(method_node: MethodNode) -> tuple:
    return tuple(param.read() for param in method_node.parameters)


def get_default_kwargs(method_node: MethodNode) -> dict:
    return {param.name: param.read() for param in method_node.parameters}


def get_dummy_method_node(
    var_name: str | None = None,
    var_description: str | None = None,
    parameters: Sequence[VariableNode] | None = None,
    returns: Sequence[VariableNode] | None = None,
    method_types: list[Callable[..., MethodNode]] | None = None,
) -> MethodNode:
    method_node = get_random_method_node(
        var_name, var_description, parameters, returns, method_types
    )

    def method_callback(**kwargs: dict[str, Any]) -> tuple:
        return tuple(param.read() for param in method_node.returns)

    method_node.callback = method_callback
    return method_node


def get_random_method_node(
    var_name: str | None = None,
    var_description: str | None = None,
    parameters: Sequence[VariableNode] | None = None,
    returns: Sequence[VariableNode] | None = None,
    method_types: list[Callable[..., MethodNode]] | None = None,
) -> MethodNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    if parameters is None:
        p = get_random_nodes(
            NUM_METHOD_PARAMS,
            [
                get_random_boolean_node,
                get_random_string_node,
                get_random_numerical_node,
            ],
        )
    else:
        p = parameters
    if returns is None:
        r = get_random_nodes(
            NUM_METHOD_RETURNS,
            [
                get_random_boolean_node,
                get_random_string_node,
                get_random_numerical_node,
            ],
        )
    else:
        r = returns
    if method_types is None:
        method_types = [MethodNode, AsyncMethodNode]

    method_node: MethodNode = random.choice(method_types)(
        name=var_name, description=var_description
    )

    for parameter in p:
        assert isinstance(parameter, VariableNode)
        method_node.add_parameter(parameter)
    for ret in r:
        assert isinstance(ret, VariableNode)
        method_node.add_return_value(ret)
    return method_node


T = TypeVar("T", bound=DataModelNode)


@overload
def get_random_node(
    node_types: Sequence[Callable[..., VariableNode]],
) -> VariableNode: ...


@overload
def get_random_node(node_types: Sequence[Callable[..., T]] | None = None) -> T: ...


def get_random_node(
    node_types: Sequence[Callable[..., DataModelNode]] | None = None,
) -> DataModelNode:
    if node_types is None:
        node_types = [
            get_random_boolean_node,
            get_random_string_node,
            get_random_numerical_node,
            get_random_folder_node,
            get_random_method_node,
            get_random_object_node,
        ]
    var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    node_type = random.choice(node_types)
    node = node_type(var_name, var_description)
    assert isinstance(node, DataModelNode)
    return node


def get_random_simple_node() -> VariableNode:
    return get_random_node(
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node]
    )


def get_random_nodes(
    number: int, node_types: list | None = None
) -> Sequence[DataModelNode]:
    nodes = []
    for i in range(number):
        nodes.append(get_random_node(node_types))
    return nodes


def get_random_simple_nodes(number: int) -> Sequence[DataModelNode]:
    return get_random_nodes(
        number,
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node],
    )
