import os
from collections.abc import Callable

import yaml

from machine_data_model.data_model import DataModel
from machine_data_model.behavior.call_method_node import CallMethodNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import ControlFlowNode
from machine_data_model.behavior.read_variable_node import (
    ReadVariableNode,
)
from machine_data_model.behavior.wait_condition_node import (
    WaitConditionNode,
    get_condition_operator,
)
from machine_data_model.behavior.write_variable_node import (
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


class DataModelBuilder:
    """
    A class to build a data model from a yaml file.
    """

    def __init__(self) -> None:
        """ "
        Initialize a new DataModelBuilder instance.
        """
        self.cache: dict[str, DataModel] = {}
        # add custom constructor
        self._add_yaml_constructors()

    def get_data_model(self, data_model_path: str) -> DataModel:
        """
        Get a data model from a yaml file.
        :param data_model_path: The path to the yaml file containing the data model.
        :return: The data model created from the yaml file.
        """
        full_path = os.path.abspath(data_model_path)

        if full_path not in self.cache:
            data_model = self._get_data_model(full_path)
            self.cache[full_path] = data_model

        return self.cache[full_path]

    def _get_folder(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> FolderNode:
        """
        Construct a folder node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed folder node.
        """
        data = loader.construct_mapping(node, deep=True)
        return FolderNode(
            **{
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "children": {child.name: child for child in data.get("children", [])},
            }
        )

    def _get_numerical_variable(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> NumericalVariableNode:
        """
        Construct a numerical variable node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed numerical variable node.
        """
        data = loader.construct_mapping(node)
        return NumericalVariableNode(
            **{
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "measure_unit": data.get("measure_unit", NoneMeasureUnits.NONE),
                "value": data.get("initial_value", 0),
            }
        )

    def _get_string_variable(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> StringVariableNode:
        """
        Construct a string variable node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed string variable node.
        """
        data = loader.construct_mapping(node)
        return StringVariableNode(
            **{
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "value": data.get("initial_value", ""),
            }
        )

    def _get_boolean_variable(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> BooleanVariableNode:
        """
        Construct a boolean variable node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed boolean variable node.
        """
        data = loader.construct_mapping(node)
        return BooleanVariableNode(
            **{
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "value": data.get("initial_value", False),
            }
        )

    def _get_object_variable(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> ObjectVariableNode:
        """
        Construct an object variable node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed object variable node.
        """
        data = loader.construct_mapping(node, deep=True)
        return ObjectVariableNode(
            **{
                "id": data.get("id", None),
                "name": data.get("name", None),
                "description": data.get("description", None),
                "properties": {prop.name: prop for prop in data.get("properties", [])},
            }
        )

    def _get_method_node(
        self,
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
        method = ctor(
            **{
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "parameters": [param for param in data.get("parameters", [])],
                "returns": [ret for ret in data.get("returns", [])],
            }
        )
        return method

    def _get_async_method_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> MethodNode:
        """
        Construct an async method node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed async method node.
        """
        return self._get_method_node(loader, node, AsyncMethodNode)

    def _get_read_variable_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> ControlFlowNode:
        """
        Construct a read variable node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed read variable node.
        """
        data = loader.construct_mapping(node, deep=True)
        return ReadVariableNode(
            variable_node=data.get("variable", ""),
            store_as=data.get("store_as", ""),
        )

    def _get_write_variable_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> ControlFlowNode:
        """ "
        Construct a write variable node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed write variable node.
        """
        data = loader.construct_mapping(node, deep=True)
        return WriteVariableNode(
            variable_node=data.get("variable", ""),
            value=data.get("value", ""),
        )

    def _get_wait_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> ControlFlowNode:
        """
        Construct a wait condition node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed wait condition node.
        """
        data = loader.construct_mapping(node, deep=True)
        return WaitConditionNode(
            variable_node=data.get("variable", ""),
            op=get_condition_operator(data.get("operator", "")),
            rhs=data.get("rhs", ""),
        )

    def _get_call_method_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> ControlFlowNode:
        """
        Construct a call method node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed call method node.
        """
        data = loader.construct_mapping(node, deep=True)
        return CallMethodNode(
            method_node=data.get("method", ""),
            args=data.get("args", []),
            kwargs=data.get("kwargs", {}),
        )

    def _get_composite_method_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> MethodNode:
        """
        Construct a composite method node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed composite method node.
        """
        data = loader.construct_mapping(node, deep=True)
        method = CompositeMethodNode(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=[param for param in data.get("parameters", [])],
            returns=[ret for ret in data.get("returns", [])],
            cfg=ControlFlow(data.get("cfg", [])),
        )
        return method

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

    def _get_data_model(self, data_model_path: str) -> DataModel:
        """ "
        Create a data model from a yaml file.
        :param data_model_path: The path to the yaml file containing the data model.
        :return: The data model.
        """
        with open(data_model_path) as file:
            data = yaml.load(file, Loader=yaml.FullLoader)
        data_model = DataModel(**data)

        return data_model

    def _add_yaml_constructors(self) -> None:
        # TODO: change old !! tags to single ! tags
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.folder_node.FolderNode",
            self._get_folder,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:FolderNode",
            self._get_folder,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.NumericalVariableNode",
            self._get_numerical_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:NumericalVariableNode",
            self._get_numerical_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.StringVariableNode",
            self._get_string_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:StringVariableNode",
            self._get_string_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.BooleanVariableNode",
            self._get_boolean_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:BooleanVariableNode",
            self._get_boolean_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.variable_node.ObjectVariableNode",
            self._get_object_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:ObjectVariableNode",
            self._get_object_variable,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.method_node.MethodNode",
            self._get_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:MethodNode",
            self._get_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.method_node.AsyncMethodNode",
            self._get_async_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:AsyncMethodNode",
            self._get_async_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.composite_method.composite_method_node.CompositeMethodNode",
            self._get_composite_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:CompositeMethodNode",
            self._get_composite_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.composite_method.read_variable_node.ReadVariableNode",
            self._get_read_variable_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:ReadVariableNode",
            self._get_read_variable_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.composite_method.write_variable_node.WriteVariableNode",
            self._get_write_variable_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:WriteVariableNode",
            self._get_write_variable_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.composite_method.wait_condition_node.WaitConditionNode",
            self._get_wait_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:WaitConditionNode",
            self._get_wait_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:python/object:machine_data_model.nodes.composite_method.call_method_node.CallMethodNode",
            self._get_call_method_node,
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:CallMethodNode",
            self._get_call_method_node,
        )
