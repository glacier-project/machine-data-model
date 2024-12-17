import os

import yaml

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.method_node import MethodNode
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

    def get_data_model(self, data_model_path: str) -> DataModel:
        """
        Get a data model from a yaml file.
        :param data_model_path: The path to the yaml file containing the data model.
        :return: The data model created from the yaml file.
        """
        full_path = os.path.abspath(data_model_path)

        if full_path not in self.cache:
            data_model = self._create_data_model(full_path)
            self.cache[full_path] = data_model

        return self.cache[full_path]

    def _construct_folder(
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

    def _construct_numerical_variable(
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
                "unit": data.get("unit", NoneMeasureUnits.NONE),
                "value": data.get("value", 0),
            }
        )

    def _construct_string_variable(
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
                "value": data.get("value", ""),
            }
        )

    def _construct_boolean_variable(
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
                "value": data.get("value", False),
            }
        )

    def _construct_object_variable(
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

    def _construct_method_node(
        self, loader: yaml.FullLoader, node: yaml.MappingNode
    ) -> MethodNode:
        """
        Construct a method node from a yaml node.
        :param loader: The yaml loader.
        :param node: The yaml node.
        :return: The constructed method node.
        """
        data = loader.construct_mapping(node, deep=True)
        return MethodNode(
            **{
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "parameters": {
                    param.name: param for param in data.get("parameters", [])
                },
                "returns": {ret.name: ret for ret in data.get("returns", [])},
            }
        )

    def _create_data_model(self, data_model_path: str) -> DataModel:
        """ "
        Create a data model from a yaml file.
        :param data_model_path: The path to the yaml file containing the data model.
        :return: The data model.
        """
        # add custom constructor
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:FolderNode",
            lambda loader, node: self._construct_folder(loader, node),
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:NumericalVariableNode",
            lambda loader, node: self._construct_numerical_variable(loader, node),
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:StringVariableNode",
            lambda loader, node: self._construct_string_variable(loader, node),
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:BooleanVariableNode",
            lambda loader, node: self._construct_boolean_variable(loader, node),
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:ObjectVariableNode",
            lambda loader, node: self._construct_object_variable(loader, node),
        )
        yaml.FullLoader.add_constructor(
            "tag:yaml.org,2002:MethodNode",
            lambda loader, node: self._construct_method_node(loader, node),
        )
        with open(data_model_path) as file:
            data = yaml.load(file, Loader=yaml.FullLoader)
        data_model = DataModel(**data)

        return data_model
