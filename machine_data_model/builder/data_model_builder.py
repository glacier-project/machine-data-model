import os
from collections.abc import Callable
from typing import Any, Hashable

import yaml

from machine_data_model.data_model import DataModel
from machine_data_model.behavior.local_execution_node import CallMethodNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import ControlFlowNode
from machine_data_model.behavior.local_execution_node import (
    ReadVariableNode,
)
from machine_data_model.behavior.local_execution_node import (
    WaitConditionNode,
    get_condition_operator,
)
from machine_data_model.behavior.local_execution_node import (
    WriteVariableNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.method_node import MethodNode, AsyncMethodNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
)
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
    WaitRemoteEventNode,
    WriteRemoteVariableNode,
    ReadRemoteVariableNode,
)


def _build_kwargs(data: dict[Hashable, Any], kwargs: dict) -> dict[str, Any]:
    for key, value in data.items():
        if key not in kwargs:
            raise ValueError(f"Unexpected key: {key}")

        kwargs[key] = value
    return kwargs


def _get_folder(loader: yaml.FullLoader, node: yaml.MappingNode) -> FolderNode:
    """
    Construct a folder node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed folder node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {"id": None, "name": "", "description": "", "children": []}
    kwargs = _build_kwargs(data, allowed_keys)
    kwargs["children"] = {child.name: child for child in kwargs["children"]}

    return FolderNode(**kwargs)


def _get_numerical_variable(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> NumericalVariableNode:
    """
    Construct a numerical variable node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed numerical variable node.
    """
    data = loader.construct_mapping(node)
    allowed_keys = {
        "id": None,
        "name": "",
        "description": "",
        "measure_unit": NoneMeasureUnits.NONE,
        "initial_value": None,
        "default_value": None,
    }
    kwargs = _build_kwargs(data, allowed_keys)
    kwargs["value"] = (
        kwargs["initial_value"] if kwargs["initial_value"] is not None else 0
    )
    del kwargs["initial_value"]
    del kwargs["default_value"]
    return NumericalVariableNode(**kwargs)


def _get_string_variable(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> StringVariableNode:
    """
    Construct a string variable node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed string variable node.
    """
    data = loader.construct_mapping(node)
    allowed_keys = {
        "id",
        "name",
        "description",
        "measure_unit",
        "initial_value",
        "default_value",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in StringVariableNode: {', '.join(extra_keys)}"
        )
    return StringVariableNode(
        **{
            "id": data.get("id", None),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "value": data.get("initial_value", ""),
        }
    )


def _get_boolean_variable(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> BooleanVariableNode:
    """
    Construct a boolean variable node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed boolean variable node.
    """
    data = loader.construct_mapping(node)
    allowed_keys = {
        "id",
        "name",
        "description",
        "measure_unit",
        "initial_value",
        "default_value",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in BooleanVariableNode: {', '.join(extra_keys)}"
        )
    return BooleanVariableNode(
        **{
            "id": data.get("id", None),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "value": data.get("initial_value", False),
        }
    )


def _get_object_variable(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> ObjectVariableNode:
    """
    Construct an object variable node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed object variable node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "id",
        "name",
        "measure_unit",
        "description",
        "properties",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in ObjectVariableNode: {', '.join(extra_keys)}"
        )
    return ObjectVariableNode(
        **{
            "id": data.get("id", None),
            "name": data.get("name", None),
            "description": data.get("description", None),
            "properties": {prop.name: prop for prop in data.get("properties", [])},
        }
    )


def _get_method_node(
    loader: yaml.FullLoader,
    node: yaml.MappingNode,
    ctor: Callable[..., MethodNode] = MethodNode,
) -> MethodNode:
    """
    Construct a method node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed method node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "id",
        "name",
        "description",
        "parameters",
        "returns",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(f"Unexpected keys in MethodNode: {', '.join(extra_keys)}")
    method = ctor(
        **{
            "id": data.get("id", None),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "parameters": [param for param in data.get("parameters", [])],
            "returns": [ret for ret in data.get("returns", [])],
        }
    )
    return method


def _get_async_method_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> MethodNode:
    """
    Construct an async method node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed async method node.
    """
    return _get_method_node(loader, node, AsyncMethodNode)


def _get_read_variable_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """
    Construct a read variable node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed read variable node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "variable",
        "store_as",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in ReadVariableNode: {', '.join(extra_keys)}"
        )
    return ReadVariableNode(
        variable_node=data.get("variable", ""),
        store_as=data.get("store_as", ""),
    )


def _get_write_variable_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """ "
    Construct a write variable node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed write variable node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "variable",
        "value",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in WriteVariableNode: {', '.join(extra_keys)}"
        )
    return WriteVariableNode(
        variable_node=data.get("variable", ""),
        value=data.get("value", ""),
    )


def _get_wait_node(loader: yaml.FullLoader, node: yaml.MappingNode) -> ControlFlowNode:
    """
    Construct a wait condition node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed wait condition node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "variable",
        "operator",
        "rhs",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in WaitConditionNode: {', '.join(extra_keys)}"
        )
    return WaitConditionNode(
        variable_node=data.get("variable", ""),
        op=get_condition_operator(data.get("operator", "")),
        rhs=data.get("rhs", ""),
    )


def _get_call_method_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """
    Construct a call method node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed call method node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "method",
        "args",
        "kwargs",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(f"Unexpected keys in CallMethodNode: {', '.join(extra_keys)}")
    return CallMethodNode(
        method_node=data.get("method", ""),
        args=data.get("args", []),
        kwargs=data.get("kwargs", {}),
    )


def _get_call_remote_method_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> CallRemoteMethodNode:
    data = loader.construct_mapping(node, deep=True)
    return CallRemoteMethodNode(
        method_node=data["method"],
        remote_id=data["remote_id"],
        args=data.get("args", []),
        kwargs=data.get("kwargs", {}),
    )


def _get_read_remote_variable_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> ReadRemoteVariableNode:
    data = loader.construct_mapping(node, deep=True)
    return ReadRemoteVariableNode(
        variable_node=data["variable"],
        remote_id=data["remote_id"],
        store_as=data.get("store_as", ""),
    )


def _get_write_remote_variable_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> WriteRemoteVariableNode:
    data = loader.construct_mapping(node, deep=True)
    return WriteRemoteVariableNode(
        variable_node=data["variable"],
        remote_id=data["remote_id"],
        value=data["value"],
    )


def _get_wait_remote_event_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    data = loader.construct_mapping(node, deep=True)
    return WaitRemoteEventNode(
        variable_node=data["variable"],
        op=get_condition_operator(data["operator"]),
        rhs=data["rhs"],
        remote_id=data["remote_id"],
    )


def _get_composite_method_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> MethodNode:
    """
    Construct a composite method node from a yaml node.
    :param loader: The yaml loader.
    :param node: The yaml node.
    :return: The constructed composite method node.
    """
    data = loader.construct_mapping(node, deep=True)
    allowed_keys = {
        "id",
        "name",
        "description",
        "parameters",
        "returns",
        "cfg",
    }
    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(
            f"Unexpected keys in CompositeMethodNode: {', '.join(extra_keys)}"
        )
    method = CompositeMethodNode(
        id=data.get("id", None),
        name=data.get("name", ""),
        description=data.get("description", ""),
        parameters=[param for param in data.get("parameters", [])],
        returns=[ret for ret in data.get("returns", [])],
        cfg=ControlFlow(data.get("cfg", [])),
    )
    return method


yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.folder_node.FolderNode",
    _get_folder,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:FolderNode",
    _get_folder,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.NumericalVariableNode",
    _get_numerical_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:NumericalVariableNode",
    _get_numerical_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.StringVariableNode",
    _get_string_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:StringVariableNode",
    _get_string_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.BooleanVariableNode",
    _get_boolean_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:BooleanVariableNode",
    _get_boolean_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.ObjectVariableNode",
    _get_object_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:ObjectVariableNode",
    _get_object_variable,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.method_node.MethodNode",
    _get_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:MethodNode",
    _get_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.method_node.AsyncMethodNode",
    _get_async_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:AsyncMethodNode",
    _get_async_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.nodes.composite_method.composite_method_node.CompositeMethodNode",
    _get_composite_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:CompositeMethodNode",
    _get_composite_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.local_execution_node.ReadVariableNode",
    _get_read_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:ReadVariableNode",
    _get_read_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.local_execution_node.WriteVariableNode",
    _get_write_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:WriteVariableNode",
    _get_write_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.local_execution_node.WaitConditionNode",
    _get_wait_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:WaitConditionNode",
    _get_wait_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.local_execution_node.CallMethodNode",
    _get_call_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:CallMethodNode",
    _get_call_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.remote_execution_node.CallRemoteMethodNode",
    _get_call_remote_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:CallRemoteMethodNode",
    _get_call_remote_method_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.remote_execution_node.ReadRemoteVariableNode",
    _get_read_remote_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:ReadRemoteVariableNode",
    _get_read_remote_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.remote_execution_node.WriteRemoteVariableNode",
    _get_write_remote_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:WriteRemoteVariableNode",
    _get_write_remote_variable_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:WaitRemoteEventNode",
    _get_wait_remote_event_node,
)
yaml.FullLoader.add_constructor(
    "tag:yaml.org,2002:python/object:machine_data_model.behavior.remote_execution_node.WaitRemoteEventNode",
    _get_wait_remote_event_node,
)


class DataModelBuilder:
    """
    A class to build a data model from a yaml file.
    """

    def __init__(self) -> None:
        """ "
        Initialize a new DataModelBuilder instance.
        """
        self.cache: dict[str, DataModel] = {}

    def from_string(self, data_model_string: str) -> DataModel:
        """
        Create a data model from a YAML string.

        :param data_model_string: The YAML string containing the data model.
        :return: The data model.
        """

        # Load the YAML string
        data = yaml.load(data_model_string, Loader=yaml.FullLoader)

        # Create the data model
        data_model = DataModel(**data)

        return data_model

    def _load_data_model(self, data_model_path: str) -> DataModel:
        """
        Create a data model from a yaml file.
        :param data_model_path: The path to the yaml file containing the data model.
        :return: The data model.
        """
        with open(data_model_path) as file:
            data = yaml.load(file, Loader=yaml.FullLoader)
        data_model = DataModel(**data)

        return data_model

    def get_data_model(self, data_model_path: str) -> DataModel:
        """
        Get a data model from a yaml file.
        :param data_model_path: The path to the yaml file containing the data model.
        :return: The data model created from the yaml file.
        """
        full_path = os.path.abspath(data_model_path)

        if full_path not in self.cache:
            data_model = self._load_data_model(full_path)
            self.cache[full_path] = data_model

        return self.cache[full_path]
