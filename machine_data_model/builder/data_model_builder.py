"""
Data model builder for creating machine data models from YAML files.

This module provides functionality to build data models, including nodes and
control flows, from YAML configuration files using custom YAML constructors.
"""

import os
from collections.abc import Callable, Hashable
from typing import Any

import yaml
from machine_data_model.nodes.connectors.opcua_connector import OpcuaConnector

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import ControlFlowNode
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
    WaitConditionNode,
    WriteVariableNode,
    get_condition_operator,
)
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
    ReadRemoteVariableNode,
    WaitRemoteEventNode,
    WriteRemoteVariableNode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.connectors.remote_resource_spec import (
    OpcuaRemoteResourceSpec,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
)


def _build_kwargs(
    data: dict[Hashable, Any], default_kwargs: dict[str, Any]
) -> dict[str, Any]:
    """
    Build kwargs by merging data with default values and validating keys.

    Args:
        data (dict[Hashable, Any]):
            Input data from YAML
        default_kwargs (dict[str, Any]):
            Default values for all allowed keys

    Returns:
        dict[str, Any]:
            Merged kwargs dictionary

    Raises:
        ValueError:
            If unexpected keys are found in data

    """
    unexpected_keys = set(data.keys()) - set(default_kwargs.keys())
    if unexpected_keys:
        raise ValueError(
            f"Unexpected keys: {', '.join(map(str, unexpected_keys))}. "
            f"Allowed keys: {', '.join(default_kwargs.keys())}"
        )

    kwargs = default_kwargs.copy()
    for key, value in data.items():
        kwargs[str(key)] = value
    return kwargs


def _get_folder(loader: yaml.SafeLoader, node: yaml.MappingNode) -> FolderNode:
    """
    Construct a folder node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        FolderNode:
            The constructed folder node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "id": None,
        "name": "",
        "description": "",
        "children": [],
        "connector_name": None,
        "remote_path": None,
        "remote_resource_spec": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    kwargs["children"] = {child.name: child for child in kwargs["children"]}

    return FolderNode(**kwargs)


def _get_numerical_variable(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> NumericalVariableNode:
    """
    Construct a numerical variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        NumericalVariableNode:
            The constructed numerical variable node.

    """
    data = loader.construct_mapping(node)
    default_kwargs = {
        "id": None,
        "name": "",
        "description": "",
        "measure_unit": NoneMeasureUnits.NONE,
        "initial_value": None,
        "default_value": None,
        "connector_name": None,
        "remote_path": None,
        "notify_subscribers_only_if_value_changed": None,
        "remote_resource_spec": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    kwargs["value"] = (
        kwargs["initial_value"] if kwargs["initial_value"] is not None else 0
    )
    del kwargs["initial_value"]
    del kwargs["default_value"]
    return NumericalVariableNode(**kwargs)


def _get_string_variable(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> StringVariableNode:
    """
    Construct a string variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        StringVariableNode:
            The constructed string variable node.

    """
    data = loader.construct_mapping(node)
    default_kwargs = {
        "id": None,
        "name": "",
        "description": "",
        "initial_value": "",
        "default_value": "",
        "connector_name": None,
        "remote_path": None,
        "notify_subscribers_only_if_value_changed": None,
        "remote_resource_spec": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    kwargs["value"] = (
        kwargs["initial_value"] if kwargs["initial_value"] is not None else ""
    )
    del kwargs["initial_value"]
    del kwargs["default_value"]

    return StringVariableNode(**kwargs)


def _get_boolean_variable(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> BooleanVariableNode:
    """
    Construct a boolean variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        BooleanVariableNode:
            The constructed boolean variable node.

    """
    data = loader.construct_mapping(node)
    default_kwargs = {
        "id": None,
        "name": "",
        "description": "",
        "initial_value": False,
        "default_value": False,
        "connector_name": None,
        "remote_path": None,
        "notify_subscribers_only_if_value_changed": None,
        "remote_resource_spec": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    kwargs["value"] = (
        kwargs["initial_value"] if kwargs["initial_value"] is not None else False
    )
    del kwargs["initial_value"]
    del kwargs["default_value"]
    return BooleanVariableNode(**kwargs)


def _get_object_variable(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> ObjectVariableNode:
    """
    Construct an object variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ObjectVariableNode:
            The constructed object variable node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "id": None,
        "name": "",
        "description": "",
        "properties": [],
        "connector_name": None,
        "remote_path": None,
        "notify_subscribers_only_if_value_changed": None,
        "remote_resource_spec": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    kwargs["properties"] = {prop.name: prop for prop in kwargs["properties"]}
    return ObjectVariableNode(**kwargs)


def _get_method_node(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    ctor: Callable[..., MethodNode] = MethodNode,
) -> MethodNode:
    """
    Construct a method node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.
        ctor:
            The constructor to use for creating the method node.

    Returns:
        MethodNode:
            The constructed method node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "id": None,
        "name": "",
        "description": "",
        "parameters": [],
        "returns": [],
        "connector_name": None,
        "remote_path": None,
        "remote_resource_spec": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return ctor(**kwargs)


def _get_async_method_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> MethodNode:
    """
    Construct an async method node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        MethodNode:
            The constructed async method node.

    """
    return _get_method_node(loader, node, AsyncMethodNode)


def _get_read_variable_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """
    Construct a read variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ControlFlowNode:
            The constructed read variable node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "variable": "",
        "store_as": "",
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return ReadVariableNode(
        variable_node=kwargs["variable"],
        store_as=kwargs["store_as"],
    )


def _get_write_variable_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """
    Construct a write variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ControlFlowNode:
            The constructed write variable node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "variable": "",
        "value": "",
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return WriteVariableNode(
        variable_node=kwargs["variable"],
        value=kwargs["value"],
    )


def _get_wait_node(loader: yaml.SafeLoader, node: yaml.MappingNode) -> ControlFlowNode:
    """
    Construct a wait condition node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ControlFlowNode:
            The constructed wait condition node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "variable": "",
        "operator": "",
        "rhs": "",
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return WaitConditionNode(
        variable_node=kwargs["variable"],
        op=get_condition_operator(kwargs["operator"]),
        rhs=kwargs["rhs"],
    )


def _get_call_method_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """
    Construct a call method node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ControlFlowNode:
            The constructed call method node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "method": "",
        "args": [],
        "kwargs": {},
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return CallMethodNode(
        method_node=kwargs["method"],
        args=kwargs["args"],
        kwargs=kwargs["kwargs"],
    )


def _get_call_remote_method_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> CallRemoteMethodNode:
    """
    Construct a call remote method node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        CallRemoteMethodNode:
            The constructed call remote method node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "method": "",
        "remote_id": "",
        "args": [],
        "kwargs": {},
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return CallRemoteMethodNode(
        method_node=kwargs["method"],
        remote_id=kwargs["remote_id"],
        args=kwargs["args"],
        kwargs=kwargs["kwargs"],
    )


def _get_read_remote_variable_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> ReadRemoteVariableNode:
    """
    Construct a read remote variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ReadRemoteVariableNode:
            The constructed read remote variable node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "variable": "",
        "remote_id": "",
        "store_as": "",
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return ReadRemoteVariableNode(
        variable_node=kwargs["variable"],
        remote_id=kwargs["remote_id"],
        store_as=kwargs["store_as"],
    )


def _get_write_remote_variable_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> WriteRemoteVariableNode:
    """
    Construct a write remote variable node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        WriteRemoteVariableNode:
            The constructed write remote variable node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "variable": "",
        "remote_id": "",
        "value": "",
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return WriteRemoteVariableNode(
        variable_node=kwargs["variable"],
        remote_id=kwargs["remote_id"],
        value=kwargs["value"],
    )


def _get_wait_remote_event_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> ControlFlowNode:
    """
    Construct a wait remote event node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        ControlFlowNode:
            The constructed wait remote event node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "variable": "",
        "operator": "",
        "rhs": "",
        "remote_id": "",
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return WaitRemoteEventNode(
        variable_node=kwargs["variable"],
        op=get_condition_operator(kwargs["operator"]),
        rhs=kwargs["rhs"],
        remote_id=kwargs["remote_id"],
    )


def _get_composite_method_node(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> MethodNode:
    """
    Construct a composite method node from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        MethodNode:
            The constructed composite method node.

    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "id": None,
        "name": "",
        "description": "",
        "parameters": [],
        "returns": [],
        "cfg": [],
    }
    kwargs = _build_kwargs(data, default_kwargs)
    kwargs["cfg"] = ControlFlow(kwargs["cfg"])
    return CompositeMethodNode(**kwargs)


def _get_opcua_connector_node(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> OpcuaConnector:
    """
    Construct an OPC-UA Connector from a yaml node.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        OpcuaConnector:
            The constructed OPC-UA Connector.
    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "name": None,
        "ip": "127.0.0.1",
        "ip_env_var": None,
        "port": 4840,
        "port_env_var": None,
        "security_policy": None,
        "host_name": None,
        "client_app_uri": None,
        "certificate_file_path": None,
        "private_key_file_path": None,
        "trust_store_certificates_paths": None,
        "username": None,
        "username_env_var": None,
        "password": None,
        "password_env_var": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return OpcuaConnector(**kwargs)


def _get_opcua_remote_resource_spec(
    loader: yaml.FullLoader, node: yaml.MappingNode
) -> OpcuaRemoteResourceSpec:
    """
    Construct an object with node settings that are OPC UA specific.

    Args:
        loader:
            The yaml loader.
        node:
            The yaml node.

    Returns:
        OpcuaRemoteResourceSpec:
            The object with the OPC UA node's settings.
    """
    data = loader.construct_mapping(node, deep=True)
    default_kwargs = {
        "node_id": None,
        "namespace": None,
    }
    kwargs = _build_kwargs(data, default_kwargs)
    return OpcuaRemoteResourceSpec(**kwargs)


def _register_yaml_constructors() -> None:
    """
    Register all YAML constructors for data model building.
    """
    constructors = {
        FolderNode: _get_folder,
        NumericalVariableNode: _get_numerical_variable,
        StringVariableNode: _get_string_variable,
        BooleanVariableNode: _get_boolean_variable,
        ObjectVariableNode: _get_object_variable,
        MethodNode: _get_method_node,
        AsyncMethodNode: _get_async_method_node,
        CompositeMethodNode: _get_composite_method_node,
        ReadVariableNode: _get_read_variable_node,
        WriteVariableNode: _get_write_variable_node,
        WaitConditionNode: _get_wait_node,
        CallMethodNode: _get_call_method_node,
        CallRemoteMethodNode: _get_call_remote_method_node,
        ReadRemoteVariableNode: _get_read_remote_variable_node,
        WriteRemoteVariableNode: _get_write_remote_variable_node,
        WaitRemoteEventNode: _get_wait_remote_event_node,
        OpcuaConnector: _get_opcua_connector_node,
        OpcuaRemoteResourceSpec: _get_opcua_remote_resource_spec,
    }

    for node, constructor in constructors.items():
        tag = node.__name__
        module = node.__module__
        yaml.SafeLoader.add_constructor(f"tag:yaml.org,2002:{tag}", constructor)
        yaml.SafeLoader.add_constructor(
            f"tag:yaml.org,2002:python/object:{module}.{tag}", constructor
        )


_register_yaml_constructors()


class DataModelBuilder:
    """
    A class to build a data model from a yaml file.

    Attributes:
        cache (dict[str, DataModel]):
            A cache mapping file paths to loaded DataModel instances.

    """

    cache: dict[str, DataModel]

    def __init__(self) -> None:
        """
        Initialize a new DataModelBuilder instance.
        """
        self.cache = {}

    def from_string(self, data_model_string: str) -> DataModel:
        """
        Create a data model from a YAML string.

        Args:
            data_model_string:
                The YAML string containing the data model.

        Returns:
            DataModel:
                The data model.

        """
        # Load the YAML string
        data = yaml.load(data_model_string, Loader=yaml.SafeLoader)

        # Create the data model
        data_model = DataModel(**data)

        return data_model

    def _load_data_model(self, data_model_path: str) -> DataModel:
        """
        Create a data model from a yaml file.

        Args:
            data_model_path:
                The path to the yaml file containing the data model.

        Returns:
            DataModel:
                The data model.

        """
        with open(data_model_path) as file:
            data = yaml.load(file, Loader=yaml.SafeLoader)
        data_model = DataModel(**data)

        return data_model

    def get_data_model(self, data_model_path: str) -> DataModel:
        """
        Get a data model from a yaml file.

        Args:
            data_model_path:
                The path to the yaml file containing the data model.

        Returns:
            DataModel:
                The data model created from the yaml file.

        """
        full_path = os.path.abspath(data_model_path)

        if full_path not in self.cache:
            data_model = self._load_data_model(full_path)
            self.cache[full_path] = data_model

        return self.cache[full_path]
