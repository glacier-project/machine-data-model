import os

import yaml

from machine_data_model.data_model import DataModel
from machine_data_model.behavior.call_method_node import CallMethodNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.read_variable_node import (
    ReadVariableNode,
)
from machine_data_model.behavior.wait_condition_node import (
    WaitConditionNode,
)
from machine_data_model.behavior.write_variable_node import (
    WriteVariableNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import MethodNode, AsyncMethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    BooleanVariableNode,
    ObjectVariableNode,
    StringVariableNode,
)
from machine_data_model.behavior.remote_execution_node import (
    ReadRemoteVariableNode,
    WriteRemoteVariableNode,
    CallRemoteMethodNode,
)


def _data_model_representer(
    dumper: yaml.Dumper, data_model: DataModel
) -> yaml.nodes.MappingNode:
    """
    Represent a DataModel as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param data_model: The DataModel instance to represent.
    :return: A YAML mapping node representing the DataModel.
    """
    return dumper.represent_mapping(
        yaml.BaseDumper.DEFAULT_MAPPING_TAG,
        {
            "name": data_model.name,
            "machine_category": data_model.machine_category,
            "machine_type": data_model.machine_type,
            "machine_model": data_model.machine_model,
            "description": data_model.description,
            "root": data_model.root,
        },
    )


def _folder_node_representer(
    dumper: yaml.Dumper, node: FolderNode
) -> yaml.nodes.MappingNode:
    """
    Represent a FolderNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The FolderNode instance to represent.
    :return: A YAML mapping node representing the FolderNode.
    """
    children = [child for child in node.children.values()]
    return dumper.represent_mapping(
        "tag:yaml.org,2002:FolderNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "children": children,
        },
    )


def _numerical_variable_node_representer(
    dumper: yaml.Dumper, node: NumericalVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a NumericalVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The NumericalVariableNode instance to represent.
    :return: A YAML mapping node representing the NumericalVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:NumericalVariableNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "initial_value": node.value,
            "measure_unit": str(node.get_measure_unit()),
        },
    )


def _boolean_variable_node_representer(
    dumper: yaml.Dumper, node: BooleanVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a BooleanVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The BooleanVariableNode instance to represent.
    :return: A YAML mapping node representing the BooleanVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:BooleanVariableNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "initial_value": node.value,
        },
    )


def _string_variable_node_representer(
    dumper: yaml.Dumper, node: StringVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a StringVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The StringVariableNode instance to represent.
    :return: A YAML mapping node representing the StringVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:StringVariableNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "initial_value": node.value,
        },
    )


def _object_node_representer(
    dumper: yaml.Dumper, node: ObjectVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a ObjectVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The ObjectVariableNode instance to represent.
    :return: A YAML mapping node representing the ObjectVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:ObjectVariableNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "properties": list(node.get_properties().values()),
        },
    )


def _method_node_representer(
    dumper: yaml.Dumper, node: MethodNode
) -> yaml.nodes.MappingNode:
    """
    Represent a MethodNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The MethodNode instance to represent.
    :return: A YAML mapping node representing the MethodNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:MethodNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "parameters": node.parameters,
            "returns": node.returns,
        },
    )


def _async_method_node_representer(
    dumper: yaml.Dumper, node: AsyncMethodNode
) -> yaml.nodes.MappingNode:
    """
    Represent an AsyncMethodNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The AsyncMethodNode instance to represent.
    :return: A YAML mapping node representing the AsyncMethodNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:AsyncMethodNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "parameters": node.parameters,
            "returns": node.returns,
        },
    )


def _composite_method_node_representer(
    dumper: yaml.Dumper, node: CompositeMethodNode
) -> yaml.nodes.MappingNode:
    """
    Represent a CompositeMethodNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The CompositeMethodNode instance to represent.
    :return: A YAML mapping node representing the CompositeMethodNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:CompositeMethodNode",
        {
            "id": node.id,
            "name": node.name,
            "description": node.description,
            "parameters": node.parameters,
            "returns": node.returns,
            "cfg": node.cfg,
        },
    )


def _control_flow_graph_representer(
    dumper: yaml.Dumper, node: ControlFlow
) -> yaml.nodes.SequenceNode:
    """
    Represent a ControlFlow as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The ControlFlow instance to represent.
    :return: A YAML mapping node representing the ControlFlow.
    """
    return dumper.represent_sequence(
        yaml.BaseDumper.DEFAULT_SEQUENCE_TAG,
        node.nodes(),
    )


def _read_variable_node_representer(
    dumper: yaml.Dumper, node: ReadVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a ReadVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The ReadVariableNode instance to represent.
    :return: A YAML mapping node representing the ReadVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:ReadVariableNode",
        {"variable": node.node, "store_as": node.store_as},
    )


def _write_variable_node_representer(
    dumper: yaml.Dumper, node: WriteVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a WriteVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The WriteVariableNode instance to represent.
    :return: A YAML mapping node representing the WriteVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:WriteVariableNode",
        {"variable": node.node, "value": node.value},
    )


def _wait_condition_node_representer(
    dumper: yaml.Dumper, node: WaitConditionNode
) -> yaml.nodes.MappingNode:
    """
    Represent a WaitConditionNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The WaitConditionNode instance to represent.
    :return: A YAML mapping node representing the WaitConditionNode.
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
    """
    Represent a CallMethodNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The CallMethodNode instance to represent.
    :return: A YAML mapping node representing the CallMethodNode.
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
    """
    Represent a CallRemoteMethodNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The CallRemoteMethodNode instance to represent.
    :return: A YAML mapping node representing the CallRemoteMethodNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:CallRemoteMethodNode",
        {
            "method": node.node,
            "sender_id": node.sender_id,
            "remote_id": node.remote_id,
            "args": node.args,
            "kwargs": node.kwargs,
        },
    )


def _read_remote_variable_node_representer(
    dumper: yaml.Dumper, node: ReadRemoteVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a ReadRemoteVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The ReadRemoteVariableNode instance to represent.
    :return: A YAML mapping node representing the ReadRemoteVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:ReadRemoteVariableNode",
        {
            "variable": node.node,
            "sender_id": node.sender_id,
            "remote_id": node.remote_id,
            "store_as": node.store_as,
        },
    )


def _write_remote_variable_node_representer(
    dumper: yaml.Dumper, node: WriteRemoteVariableNode
) -> yaml.nodes.MappingNode:
    """
    Represent a WriteRemoteVariableNode as a YAML mapping node.
    :param dumper: The YAML dumper instance.
    :param node: The WriteRemoteVariableNode instance to represent.
    :return: A YAML mapping node representing the WriteRemoteVariableNode.
    """
    return dumper.represent_mapping(
        "tag:yaml.org,2002:WriteRemoteVariableNode",
        {
            "variable": node.node,
            "sender_id": node.sender_id,
            "remote_id": node.remote_id,
            "value": node.value,
        },
    )


# Register the representers for the custom classes
yaml.add_representer(DataModel, _data_model_representer)
yaml.add_representer(FolderNode, _folder_node_representer)
yaml.add_representer(NumericalVariableNode, _numerical_variable_node_representer)
yaml.add_representer(BooleanVariableNode, _boolean_variable_node_representer)
yaml.add_representer(StringVariableNode, _string_variable_node_representer)
yaml.add_representer(ObjectVariableNode, _object_node_representer)
yaml.add_representer(MethodNode, _method_node_representer)
yaml.add_representer(AsyncMethodNode, _async_method_node_representer)
yaml.add_representer(CompositeMethodNode, _composite_method_node_representer)
yaml.add_representer(ControlFlow, _control_flow_graph_representer)
yaml.add_representer(ReadVariableNode, _read_variable_node_representer)
yaml.add_representer(WriteVariableNode, _write_variable_node_representer)
yaml.add_representer(WaitConditionNode, _wait_condition_node_representer)
yaml.add_representer(CallMethodNode, _call_method_node_representer)
yaml.add_representer(CallRemoteMethodNode, _call_remote_method_node_representer)
yaml.add_representer(ReadRemoteVariableNode, _read_remote_variable_node_representer)
yaml.add_representer(WriteRemoteVariableNode, _write_remote_variable_node_representer)


class DataModelDumper:
    """
    A class to dump the machine data model to a YAML file.

    :ivar data_model: The machine data model to dump.
    """

    def __init__(self, data_model: DataModel) -> None:
        self.data_model = data_model

    def dump(self) -> str:
        """
        Dump the machine data model to a YAML string.

        :return: The YAML string representation of the machine data model.
        """
        data_model_str = yaml.dump(self.data_model)
        assert isinstance(data_model_str, str)
        return data_model_str

    def dumps(self, file_path: str) -> None:
        """
        Dumps the machine data model to a YAML file.

        :param file_path: The path to the YAML file.
        :raises FileNotFoundError: If the file path is not valid.
        :raises IOError: If there is an error writing to the file.
        :return: None
        """
        base_dir = os.path.dirname(file_path)
        os.makedirs(base_dir, exist_ok=True)

        with open(file_path, "w") as file:
            yaml.dump(self.data_model, file)
