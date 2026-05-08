"""Data model dumper module for serializing machine data models to YAML format.

This module provides functionality to convert machine data model objects back
into YAML representations, including custom representers for all node types and
control flow elements.
"""

import os
from typing import Any

import yaml

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
    WaitConditionNode,
    WriteVariableNode,
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
from machine_data_model.nodes.connectors.opcua.opcua_connector import (
    OpcuaConnector,
    OpcuaRemoteResourceSpec,
)
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
)


def _data_model_representer(
    dumper: yaml.Dumper, data_model: DataModel
) -> yaml.nodes.MappingNode:
    """Represent a DataModel as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        data_model (DataModel):
            The DataModel instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the DataModel.

    """
    return dumper.represent_mapping(
        yaml.BaseDumper.DEFAULT_MAPPING_TAG,
        {
            "name": data_model.name,
            "machine_category": data_model.machine_category,
            "machine_type": data_model.machine_type,
            "machine_model": data_model.machine_model,
            "description": data_model.description,
            "connectors": list(data_model.connectors.values()),
            "root": data_model.root,
        },
    )


def _opcua_connector_representer(
    dumper: yaml.Dumper, connector: OpcuaConnector
) -> yaml.nodes.MappingNode:
    """Represent an OpcuaConnector as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        connector (OpcuaConnector):
            The OpcuaConnector instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the OpcuaConnector.
    """
    connector_dict: dict[str, Any] = {"name": connector.name}

    if connector.ip_env_var:
        connector_dict["ip_env_var"] = connector.ip_env_var
    else:
        connector_dict["ip"] = connector.ip
    if connector.port_env_var:
        connector_dict["port_env_var"] = connector.port_env_var
    else:
        connector_dict["port"] = connector.port
    if connector.security_policy:
        connector_dict["security_policy"] = connector.security_policy
    if connector.client_app_uri != connector.get_default_client_app_uri():
        connector_dict["client_app_uri"] = connector.client_app_uri
    pkfp = connector.private_key_file_path
    default_pkfp = connector.get_default_private_key_file_path()
    if pkfp != default_pkfp:
        connector_dict["private_key_file_path"] = pkfp
    cfp = connector.certificate_file_path
    default_cfp = connector.get_default_certificate_file_path()
    if cfp != default_cfp:
        connector_dict["certificate_file_path"] = cfp
    tcp = connector.trust_store_certificates_paths
    if tcp:
        connector_dict["trusted_certificates_path"] = tcp
    return dumper.represent_mapping(
        "tag:yaml.org,2002:OpcuaConnector", connector_dict
    )


def _get_opcua_remote_resource_spec_representer(
    dumper: yaml.Dumper, spec: OpcuaRemoteResourceSpec
) -> yaml.nodes.MappingNode:
    """Represent an OpcuaRemoteResourceSpec as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        spec (OpcuaRemoteResourceSpec):
            The OpcuaRemoteResourceSpec instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the OpcuaRemoteResourceSpec.
    """
    remote_resource_spec: dict[str, Any] = {}
    if spec.node_id:
        remote_resource_spec["node_id"] = spec.node_id
    if spec.parent_node_id:
        remote_resource_spec["parent_node_id"] = spec.parent_node_id
    elif spec.namespace:
        remote_resource_spec["namespace"] = spec.namespace
    else:
        remote_resource_spec["remote_path"] = spec.remote_path

    return dumper.represent_mapping(
        "tag:yaml.org,2002:OpcuaRemoteResourceSpec", remote_resource_spec
    )


def _get_data_model_node_common_fields(node: DataModelNode) -> dict[str, Any]:
    """Get common fields for variable nodes.

    Args:
        node (Any):
            The variable node instance.

    Returns:
        dict[str, Any]:
            A dictionary containing common fields.
    """
    data_model_node: dict[str, Any] = {
        "id": node.id,
        "name": node.name,
        "description": node.description,
    }
    if node.connector_name:
        data_model_node["connector_name"] = node.connector_name
    if node.remote_resource_spec:
        data_model_node["remote_resource_spec"] = node.remote_resource_spec
    return data_model_node


def _folder_node_representer(
    dumper: yaml.Dumper, node: FolderNode
) -> yaml.nodes.MappingNode:
    """Represent a FolderNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (FolderNode):
            The FolderNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the FolderNode.

    """
    common_fields = _get_data_model_node_common_fields(node)
    children = list(node.children.values())
    return dumper.represent_mapping(
        "tag:yaml.org,2002:FolderNode",
        {
            **common_fields,
            "children": children,
        },
    )


def _numerical_variable_node_representer(
    dumper: yaml.Dumper, node: NumericalVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a NumericalVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (NumericalVariableNode):
            The NumericalVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the NumericalVariableNode.

    """
    common_fields = _get_data_model_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:NumericalVariableNode",
        {
            **common_fields,
            "initial_value": node.value,
            "measure_unit": str(node.get_measure_unit()),
        },
    )


def _boolean_variable_node_representer(
    dumper: yaml.Dumper, node: BooleanVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a BooleanVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (BooleanVariableNode):
            The BooleanVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the BooleanVariableNode.

    """
    common_fields = _get_data_model_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:BooleanVariableNode",
        {
            **common_fields,
            "initial_value": node.value,
        },
    )


def _string_variable_node_representer(
    dumper: yaml.Dumper, node: StringVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a StringVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (StringVariableNode):
            The StringVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the StringVariableNode.

    """
    common_fields = _get_data_model_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:StringVariableNode",
        {
            **common_fields,
            "initial_value": node.value,
        },
    )


def _object_node_representer(
    dumper: yaml.Dumper, node: ObjectVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a ObjectVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (ObjectVariableNode):
            The ObjectVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the ObjectVariableNode.

    """
    common_fields = _get_data_model_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:ObjectVariableNode",
        {
            **common_fields,
            "properties": list(node.get_properties().values()),
        },
    )


def _get_method_node_common_fields(node: Any) -> dict[str, Any]:
    """Get common fields for method nodes.

    Args:
        node (Any):
            The method node instance.

    Returns:
        dict[str, Any]:
            A dictionary containing common fields.
    """
    data_model_node_common_fields = _get_data_model_node_common_fields(node)
    return {
        **data_model_node_common_fields,
        "parameters": node.parameters,
        "returns": node.returns,
    }


def _method_node_representer(
    dumper: yaml.Dumper, node: MethodNode
) -> yaml.nodes.MappingNode:
    """Represent a MethodNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (MethodNode):
            The MethodNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the MethodNode.

    """
    common_fields = _get_method_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:MethodNode",
        {**common_fields},
    )


def _async_method_node_representer(
    dumper: yaml.Dumper, node: AsyncMethodNode
) -> yaml.nodes.MappingNode:
    """Represent an AsyncMethodNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (AsyncMethodNode):
            The AsyncMethodNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the AsyncMethodNode.

    """
    common_fields = _get_method_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:AsyncMethodNode",
        {**common_fields},
    )


def _composite_method_node_representer(
    dumper: yaml.Dumper, node: CompositeMethodNode
) -> yaml.nodes.MappingNode:
    """Represent a CompositeMethodNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (CompositeMethodNode):
            The CompositeMethodNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the CompositeMethodNode.

    """
    common_fields = _get_method_node_common_fields(node)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:CompositeMethodNode",
        {
            **common_fields,
            "cfg": node.cfg,
        },
    )


def _control_flow_graph_representer(
    dumper: yaml.Dumper, node: ControlFlow
) -> yaml.nodes.SequenceNode:
    """Represent a ControlFlow as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (ControlFlow):
            The ControlFlow instance to represent.

    Returns:
        yaml.nodes.SequenceNode:
            A YAML mapping node representing the ControlFlow.

    """
    return dumper.represent_sequence(
        yaml.BaseDumper.DEFAULT_SEQUENCE_TAG,
        node.nodes(),
    )


def _read_variable_node_representer(
    dumper: yaml.Dumper, node: ReadVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a ReadVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (ReadVariableNode):
            The ReadVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the ReadVariableNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:ReadVariableNode",
        {"variable": node.node, "store_as": node.store_as},
    )


def _write_variable_node_representer(
    dumper: yaml.Dumper, node: WriteVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a WriteVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (WriteVariableNode):
            The WriteVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the WriteVariableNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:WriteVariableNode",
        {"variable": node.node, "value": node.value},
    )


def _wait_condition_node_representer(
    dumper: yaml.Dumper, node: WaitConditionNode
) -> yaml.nodes.MappingNode:
    """Represent a WaitConditionNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (WaitConditionNode):
            The WaitConditionNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the WaitConditionNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:WaitConditionNode",
        {
            "variable": node.node,
            "operator": node.op.value,
            "rhs": node.rhs,
        },
    )


def _call_method_node_representer(
    dumper: yaml.Dumper, node: CallMethodNode
) -> yaml.nodes.MappingNode:
    """Represent a CallMethodNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (CallMethodNode):
            The CallMethodNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the CallMethodNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:CallMethodNode",
        {
            "method": node.node,
            "args": node.args,
            "kwargs": node.kwargs,
        },
    )


def _call_remote_method_node_representer(
    dumper: yaml.Dumper, node: CallRemoteMethodNode
) -> yaml.nodes.MappingNode:
    """Represent a CallRemoteMethodNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (CallRemoteMethodNode):
            The CallRemoteMethodNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the CallRemoteMethodNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:CallRemoteMethodNode",
        {
            "method": node.node,
            "remote_id": node.remote_id,
            "args": node.args,
            "kwargs": node.kwargs,
        },
    )


def _read_remote_variable_node_representer(
    dumper: yaml.Dumper, node: ReadRemoteVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a ReadRemoteVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (ReadRemoteVariableNode):
            The ReadRemoteVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the ReadRemoteVariableNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:ReadRemoteVariableNode",
        {
            "variable": node.node,
            "remote_id": node.remote_id,
            "store_as": node.store_as,
        },
    )


def _write_remote_variable_node_representer(
    dumper: yaml.Dumper, node: WriteRemoteVariableNode
) -> yaml.nodes.MappingNode:
    """Represent a WriteRemoteVariableNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (WriteRemoteVariableNode):
            The WriteRemoteVariableNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the WriteRemoteVariableNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:WriteRemoteVariableNode",
        {
            "variable": node.node,
            "remote_id": node.remote_id,
            "value": node.value,
        },
    )


def _wait_remote_event_node_representer(
    dumper: yaml.Dumper, node: WaitRemoteEventNode
) -> yaml.nodes.MappingNode:
    """Represent a WaitRemoteEventNode as a YAML mapping node.

    Args:
        dumper (yaml.Dumper):
            The YAML dumper instance.
        node (WaitRemoteEventNode):
            The WaitRemoteEventNode instance to represent.

    Returns:
        yaml.nodes.MappingNode:
            A YAML mapping node representing the WaitRemoteEventNode.

    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:WaitRemoteEventNode",
        {
            "variable": node.node,
            "remote_id": node.remote_id,
            "rhs": node.rhs,
            "operator": node.op.value,
        },
    )


def _register_representers() -> None:
    """Register all custom representers for YAML serialization."""
    representers = {
        DataModel: _data_model_representer,
        OpcuaConnector: _opcua_connector_representer,
        OpcuaRemoteResourceSpec: _get_opcua_remote_resource_spec_representer,
        FolderNode: _folder_node_representer,
        NumericalVariableNode: _numerical_variable_node_representer,
        BooleanVariableNode: _boolean_variable_node_representer,
        StringVariableNode: _string_variable_node_representer,
        ObjectVariableNode: _object_node_representer,
        MethodNode: _method_node_representer,
        AsyncMethodNode: _async_method_node_representer,
        CompositeMethodNode: _composite_method_node_representer,
        ControlFlow: _control_flow_graph_representer,
        ReadVariableNode: _read_variable_node_representer,
        WriteVariableNode: _write_variable_node_representer,
        WaitConditionNode: _wait_condition_node_representer,
        CallMethodNode: _call_method_node_representer,
        CallRemoteMethodNode: _call_remote_method_node_representer,
        ReadRemoteVariableNode: _read_remote_variable_node_representer,
        WriteRemoteVariableNode: _write_remote_variable_node_representer,
        WaitRemoteEventNode: _wait_remote_event_node_representer,
    }
    for cls, representer in representers.items():
        yaml.add_representer(cls, representer)


_register_representers()


class DataModelDumper:
    """A class to dump the machine data model to a YAML file.

    Attributes:
        data_model (DataModel):
            The machine data model to dump.

    """

    def __init__(self, data_model: DataModel) -> None:
        self.data_model = data_model

    def dump(self) -> str:
        """Dump the machine data model to a YAML string.

        Returns:
            str:
                The YAML string representation of the machine data model.

        """
        data_model_str = yaml.dump(self.data_model)
        assert isinstance(data_model_str, str)
        return data_model_str

    def dumps(self, file_path: str) -> None:
        """Dumps the machine data model to a YAML file.

        Args:
            file_path (str):
                The path to the YAML file.

        Raises:
            FileNotFoundError:
                If the file path is not valid.
            IOError:
                If there is an error writing to the file.

        """
        base_dir = os.path.dirname(file_path)
        os.makedirs(base_dir, exist_ok=True)

        with open(file_path, "w") as file:
            yaml.dump(self.data_model, file)
