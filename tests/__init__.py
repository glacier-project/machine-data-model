import random
import string

from unitsnet_py.units.length import LengthUnits

from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
)

NUM_TESTS = 3
NUM_FOLDER_NODES = 3
NUM_METHOD_PARAMS = 3
NUM_METHOD_RETURNS = 2
NUM_OBJECT_PROPERTIES = 3
DEFAULT_NAME_LENGTH = 10
DEFAULT_DESCRIPTION_LENGTH = 20


def gen_random_string(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def get_random_boolean_node(
    var_name: str = None, var_description: str = None
) -> BooleanVariableNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    return BooleanVariableNode(
        name=var_name, description=var_description, value=random.choice([True, False])
    )


def get_random_string_node(
    var_name: str = None, var_description: str = None
) -> StringVariableNode:
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    return StringVariableNode(
        name=var_name, description=var_description, value=gen_random_string(10)
    )


def get_random_numerical_node(
    var_name: str = None, var_description: str = None
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


def get_random_object_node(var_name: str = None, var_description: str = None):
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
        object_node.add_property(prop)
    return object_node


def get_random_folder_node(var_name: str = None, var_description: str = None):
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    folder_node = FolderNode(name=var_name, description=var_description)
    children = get_random_nodes(
        NUM_TESTS,
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node],
    )
    for child in children:
        folder_node.add_child(child)
    return folder_node


def get_random_method_node(var_name: str = None, var_description: str = None):
    if var_name is None:
        var_name = gen_random_string(DEFAULT_NAME_LENGTH)
    if var_description is None:
        var_description = gen_random_string(DEFAULT_DESCRIPTION_LENGTH)
    method_node = MethodNode(name=var_name, description=var_description)
    parameters = get_random_nodes(
        NUM_METHOD_PARAMS,
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node],
    )
    returns = get_random_nodes(
        NUM_METHOD_RETURNS,
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node],
    )
    for parameter in parameters:
        method_node.add_parameter(parameter)
    for ret in returns:
        method_node.add_return_value(ret)
    return method_node


def get_random_node(node_types: list = None):
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
    return node_type(var_name, var_description)


def get_random_simple_node():
    return get_random_node(
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node]
    )


def get_random_nodes(number: int, node_types: list = None):
    nodes = []
    for i in range(number):
        nodes.append(get_random_node(node_types))
    return nodes


def get_random_simple_nodes(number: int):
    return get_random_nodes(
        number,
        [get_random_boolean_node, get_random_string_node, get_random_numerical_node],
    )
