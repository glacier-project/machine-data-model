from abc import abstractmethod
from typing import Any, Dict

from typing_extensions import override
from unitsnet_py.abstract_unit import AbstractMeasure

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.measurement_unit.measure_builder import (
    MeasureBuilder,
    NoneMeasureUnits,
)


class VariableNode(DataModelNode):
    """
    A VariableNode class is a node that represents an instance of a variable in the
    machine data model. Variables of the machine data model are used to store the
    current value of a machine data or parameter.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new VariableNode instance.
        :param kwargs: A dictionary containing the attributes of the variable node. The
        dictionary may contain the following keys:
            - id: The unique identifier of the variable.
            - name: The name of the variable.
            - description: The description of the variable.
        """
        super().__init__(**kwargs)
        self._pre_read_value = lambda: None
        self._post_read_value = lambda value: value
        self._pre_update_value = lambda value: value
        self._post_update_value = lambda value: True

    def read(self) -> Any:
        """
        Get the value of the variable node.
        :return: The value of the variable node.
        """
        self._pre_read_value()
        value = self._read_value()
        value = self._post_read_value(value)
        return value

    def update(self, value: Any) -> bool:
        """
        Update the value of the variable node.
        :param value: The new value of the variable node.
        :return: True if the value was updated successfully, False otherwise.
        """
        prev_value = self._read_value()
        value = self._pre_update_value(value)
        value = self._update_value(value)
        # if validation fails, restore the previous value
        if not self._post_update_value(value):
            self._update_value(prev_value)
            return False
        return True

    @abstractmethod
    def _read_value(self) -> Any:
        """
        Get the value of the variable.
        """
        pass

    @abstractmethod
    def _update_value(self, value: Any):
        """
        Update the value of the variable.
        """
        pass

    @override
    def __getitem__(self, node_name: str):
        raise NotImplementedError(
            f"f{self.__class__.__name__} does not support child nodes"
        )

    @override
    def __contains__(self, node_name: str):
        return False

    @override
    def __iter__(self):
        return iter([])


class NumericalVariableNode(VariableNode):
    """
    A NumericalVariableNode class is a node that represents an instance of a variable
    with a numerical value in the machine data model.
    """

    _measure_builder = MeasureBuilder()

    def __init__(self, **kwargs):
        """
        Initialize a new NumericalVariableNode instance.
        :param kwargs: A dictionary containing the attributes of the numerical variable
        node. The dictionary may contain the following keys:
            - id (str): The unique identifier of the numerical variable.
            - name (str): The name of the numerical variable.
            - description (str): The description of the numerical variable.
            - measure_unit (Enum): The measure unit of the numerical variable.
            - value (float): The initial value of the numerical variable.
        """
        super().__init__(**kwargs)
        self._measure_unit = NumericalVariableNode._measure_builder.get_measure_unit(
            kwargs.get("measure_unit", NoneMeasureUnits.NONE)
        )
        self._value: AbstractMeasure = (
            NumericalVariableNode._measure_builder.create_measure(
                kwargs.get("value", 0), self._measure_unit
            )
        )

    def _read_value(self) -> float:
        """
        Get the value of the numerical variable.
        :return: The value of the numerical variable.
        """
        return self._value.base_value

    def _update_value(self, value: float):
        """
        Update the value of the numerical variable.
        :param value: The new value of the numerical variable.
        :param unit: The unit of the new value. If not specified, the unit of the
        variable is used.
        """
        self._value = self._value.__class__(value, self._measure_unit)

    def __str__(self):
        return (
            f"NumericalVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, measure_unit={self._measure_unit}, "
            f"value={self._value})"
        )

    def __repr__(self):
        return self.__str__()


class StringVariableNode(VariableNode):
    """
    A StringVariableNode class is a node that represents an instance of a variable with
    a string value in the machine data model.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new StringVariableNode instance.
        :param kwargs: A dictionary containing the attributes of the string variable
        node. The dictionary may contain the following keys:
            - id (str): The unique identifier of the string variable.
            - name (str): The name of the string variable.
            - description (str): The description of the string variable.
            - value (str): The initial value of the string variable.
        """
        super().__init__(**kwargs)
        self._value: str = kwargs.get("value", "")

    def _read_value(self) -> str:
        """
        Get the value of the string variable.
        :return: The value of the string variable.
        """
        return self._value

    def _update_value(self, value: str):
        """
        Update the value of the string variable.
        :param value: The new value of the string variable.
        """
        assert isinstance(value, str)
        self._value = value

    @override
    def __getitem__(self, node_name: str):
        raise NotImplementedError("StringVariableNode does not support child nodes")

    @override
    def __contains__(self, node_name: str):
        return False

    def __str__(self):
        return (
            f"StringVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self):
        return self.__str__()


class BooleanVariableNode(VariableNode):
    """
    A BooleanVariableNode class is a node that represents an instance of a variable with
    a boolean value in the machine data model.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new BooleanVariableNode instance.
        :param kwargs: A dictionary containing the attributes of the boolean variable
        node. The dictionary may contain the following keys:
            - id (str): The unique identifier of the boolean variable.
            - name (str): The name of the boolean variable.
            - description (str): The description of the boolean variable.
            - value (bool): The initial value of the boolean variable.
        """
        super().__init__(**kwargs)
        self._value: bool = kwargs.get("value", False)

    def _read_value(self) -> bool:
        """
        Get the value of the boolean variable.
        :return: The value of the boolean variable.
        """
        return self._value

    def _update_value(self, value: bool):
        """
        Update the value of the boolean variable.
        :param value: The new value of the boolean variable.
        """
        assert isinstance(value, bool)
        self._value = value

    @override
    def __getitem__(self, node_name: str):
        raise NotImplementedError("BooleanVariableNode does not support child nodes")

    @override
    def __contains__(self, node_name: str):
        return False

    def __str__(self):
        return (
            f"BooleanVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self):
        return self.__str__()


class ObjectVariableNode(VariableNode):
    """
    An ObjectVariableNode class is a node that represents an instance of a variable with
    an object value in the machine data model.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new ObjectVariableNode instance.
        :param kwargs: A dictionary containing the attributes of the object variable
        node. The dictionary may contain the following keys:
            - id (str): The unique identifier of the object variable.
            - name (str): The name of the object variable.
            - description (str): The description of the object variable.
            - properties (dict[str,VariableNode]): The properties of the object
            variable.
            - value (dict[str,Any]): The initial value of the object variable.
        """
        super().__init__(**kwargs)
        self._properties: Dict[str, VariableNode] = kwargs.get("properties", {})
        self._update_value(kwargs.get("value", {}))

    def add_property(self, property_node: VariableNode):
        """
        Add a property to the object variable.
        :param property_node: The property node to add to the object variable.
        """
        self._properties[property_node.name] = property_node

    def remove_property(self, property_name: str):
        """
        Remove a property from the object variable.
        :param property_name: The name of the property to remove from the object
        variable.
        """
        del self._properties[property_name]

    def has_property(self, property_name: str) -> bool:
        """
        Check if the object variable has a property.
        :param property_name: The name of the property to check.
        :return: True if the object variable has the property, False otherwise.
        """
        return property_name in self._properties

    def get_property(self, property_name: str) -> VariableNode:
        """
        Get a property of the object variable.
        :param property_name: The name of the property to get.
        :return: The property of the object variable.
        """
        return self._properties[property_name]

    def _read_value(self) -> Any:
        """
        Get the value of the object variable.
        :return: The value of the object variable.
        """
        value = {}
        for property_name, property_node in self._properties.items():
            value[property_name] = property_node.read()
        return value

    def _update_value(self, value: Any):
        """
        Update the value of the object variable.
        :param value: The new value of the object variable.
        """
        for property_name, property_value in value.items():
            self._properties[property_name]._update_value(property_value)

    @override
    def __getitem__(self, property_name: str) -> VariableNode:
        """
        Get a property of the object variable.
        :param property_name: The name of the property to get.
        :return: The property of the object variable.
        """
        return self.get_property(property_name)

    @override
    def __contains__(self, property_name: str) -> bool:
        """
        Check if the object variable has a property.
        :param property_name: The name of the property to check.
        :return: True if the object variable has the property, False otherwise.
        """
        return self.has_property(property_name)

    @override
    def __iter__(self):
        """
        Iterate over the properties of the object variable.
        :return: An iterator over the properties of the object variable.
        """
        for property_node in self._properties.values():
            yield property_node

    def __str__(self):
        return (
            f"ObjectVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._read_value()})"
        )

    def __repr__(self):
        return self.__str__()
