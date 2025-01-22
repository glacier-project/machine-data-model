from abc import abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Any, Iterator

from typing_extensions import override
from unitsnet_py.abstract_unit import AbstractMeasure

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.measurement_unit.measure_builder import (
    MeasureBuilder,
    NoneMeasureUnits,
    get_measure_builder,
)


class VariableNode(DataModelNode):
    """
    A VariableNode class is a node that represents an instance of a variable in the
    machine data model. Variables of the machine data model are used to store the
    current value of a machine data or parameter.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        """
        Initialize a new VariableNode instance.
        :param kwargs: A dictionary containing the attributes of the variable node. The
        dictionary may contain the following keys:
            - id: The unique identifier of the variable.
            - name: The name of the variable.
            - description: The description of the variable.
        """
        super().__init__(id=id, name=name, description=description)
        self._pre_read_value: Callable[[], None] = lambda: None
        self._post_read_value: Callable[[Any], Any] = lambda value: value
        self._pre_update_value: Callable[[Any], Any] = lambda value: value
        self._post_update_value: Callable[[Any], bool] = lambda value: True
        self._subscribers: list[str] = []

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

    def has_subscribers(self) -> bool:
        """
        Check if the variable node has subscribers.
        :return: True if the variable node has subscribers, False otherwise.
        """
        return bool(self._subscribers)

    def subscribe(self, subscriber_id: str) -> None:
        """
        Subscribe a subscriber to the variable node.
        :param subscriber_id: The id of the subscriber to subscribe to the variable node.
        """
        self._subscribers.append(subscriber_id)

    def unsubscribe(self, subscriber_id: str) -> None:
        """
        Unsubscribe a subscriber from the variable node.
        :param subscriber_id: The id of the subscriber to unsubscribe from the variable node.
        """
        self._subscribers.remove(subscriber_id)

    @abstractmethod
    def _read_value(self) -> Any:
        """
        Get the value of the variable.
        """
        pass

    @abstractmethod
    def _update_value(self, value: Any) -> None:
        """
        Update the value of the variable.
        """
        pass

    def set_pre_read_value_callback(self, callback: Callable[[], None]) -> None:
        """
        Set a callback to be executed before reading the value of the variable.
        :param callback: The callback to be executed before reading the value of the
        variable.
        """
        self._pre_read_value = callback

    def set_post_read_value_callback(self, callback: Callable[..., Any]) -> None:
        """
        Set a callback to be executed after reading the value of the variable.
        :param callback: The callback to be executed after reading the value of the
        variable.
        """
        self._post_read_value = callback

    def set_pre_update_value_callback(self, callback: Callable[..., Any]) -> None:
        """
        Set a callback to be executed before updating the value of the variable.
        :param callback: The callback to be executed before updating the value of the
        variable.
        """
        self._pre_update_value = callback

    def set_post_update_value_callback(self, callback: Callable[..., bool]) -> None:
        """
        Set a callback to be executed after updating the value of the variable.
        :param callback: The callback to be executed after updating the value of the
        variable.
        """
        self._post_update_value = callback

    @override
    def __getitem__(self, node_name: str) -> "VariableNode":
        raise NotImplementedError(
            f"f{self.__class__.__name__} does not support child nodes"
        )

    @override
    def __contains__(self, node_name: str) -> bool:
        return False

    @override
    def __iter__(self) -> Iterator["VariableNode"]:
        for _ in []:
            yield _


class NumericalVariableNode(VariableNode):
    """
    A NumericalVariableNode class is a node that represents an instance of a variable
    with a numerical value in the machine data model.
    """

    _measure_builder: MeasureBuilder = get_measure_builder()

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        measure_unit: Enum | str = NoneMeasureUnits.NONE,
        value: float = 0,
    ):
        """
        Initialize a new NumericalVariableNode instance.
        :param id: The unique identifier of the numerical variable.
        :param name: The name of the numerical variable.
        :param description: The description of the numerical variable.
        :param measure_unit: The measure unit of the numerical variable.
        :param value: The initial value of the numerical variable.
        """
        super().__init__(id=id, name=name, description=description)
        self._measure_unit = NumericalVariableNode._measure_builder.get_measure_unit(
            measure_unit
        )
        self._value: AbstractMeasure = (
            NumericalVariableNode._measure_builder.create_measure(
                value, self._measure_unit
            )
        )

    def _read_value(self) -> float:
        """
        Get the value of the numerical variable.
        :return: The value of the numerical variable.
        """
        return self._value.base_value  # type: ignore[no-any-return]

    def _update_value(self, value: float) -> None:
        """
        Update the value of the numerical variable.
        :param value: The new value of the numerical variable.
        :param unit: The unit of the new value. If not specified, the unit of the
        variable is used.
        """
        self._value = self._value.__class__(value, self._measure_unit)

    def __str__(self) -> str:
        return (
            f"NumericalVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, measure_unit={self._measure_unit}, "
            f"value={self._value})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class StringVariableNode(VariableNode):
    """
    A StringVariableNode class is a node that represents an instance of a variable with
    a string value in the machine data model.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        value: str = "",
    ):
        """
        Initialize a new StringVariableNode instance.
        :param id: The unique identifier of the string variable.
        :param name: The name of the string variable.
        :param description: The description of the string variable.
        :param value: The initial value of the string variable.
        """
        super().__init__(id=id, name=name, description=description)
        self._value: str = value

    def _read_value(self) -> str:
        """
        Get the value of the string variable.
        :return: The value of the string variable.
        """
        return self._value

    def _update_value(self, value: str) -> None:
        """
        Update the value of the string variable.
        :param value: The new value of the string variable.
        """
        assert isinstance(value, str)
        self._value = value

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        raise NotImplementedError("StringVariableNode does not support child nodes")

    @override
    def __contains__(self, node_name: str) -> bool:
        return False

    def __str__(self) -> str:
        return (
            f"StringVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class BooleanVariableNode(VariableNode):
    """
    A BooleanVariableNode class is a node that represents an instance of a variable with
    a boolean value in the machine data model.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        value: bool = False,
    ):
        """
        Initialize a new BooleanVariableNode instance.
        :param id: The unique identifier of the boolean variable.
        :param name: The name of the boolean variable.
        :param description: The description of the boolean variable.
        :param value: The initial value of the boolean variable.
        """
        super().__init__(id, name, description)
        self._value: bool = value

    def _read_value(self) -> bool:
        """
        Get the value of the boolean variable.
        :return: The value of the boolean variable.
        """
        return self._value

    def _update_value(self, value: bool) -> None:
        """
        Update the value of the boolean variable.
        :param value: The new value of the boolean variable.
        """
        assert isinstance(value, bool)
        self._value = value

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        raise NotImplementedError("BooleanVariableNode does not support child nodes")

    @override
    def __contains__(self, node_name: str) -> bool:
        return False

    def __str__(self) -> str:
        return (
            f"BooleanVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self) -> str:
        return self.__str__()


class ObjectVariableNode(VariableNode):
    """
    An ObjectVariableNode class is a node that represents an instance of a variable with
    an object value in the machine data model.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        properties: dict[str, VariableNode] | None = None,
        value: dict[str, Any] | None = None,
    ):
        """
        Initialize a new ObjectVariableNode instance.
        :param id: The unique identifier of the object variable.
        :param name: The name of the object variable.
        :param description: The description of the object variable.
        :param properties: The properties of the object variable.
        :param value: The initial value of the object variable.
        """
        super().__init__(id=id, name=name, description=description)
        self._properties: dict[str, VariableNode] = (
            properties if properties is not None else {}
        )
        if value is not None:
            self._update_value(value)

    def add_property(self, property_node: VariableNode) -> None:
        """
        Add a property to the object variable.
        :param property_node: The property node to add to the object variable.
        """
        self._properties[property_node.name] = property_node

    def remove_property(self, property_name: str) -> None:
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

    def _update_value(self, value: dict) -> None:
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
    def __iter__(self) -> Iterator[VariableNode]:
        """
        Iterate over the properties of the object variable.
        :return: An iterator over the properties of the object variable.
        """
        for property_node in self._properties.values():
            yield property_node

    def __str__(self) -> str:
        return (
            f"ObjectVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._read_value()})"
        )

    def __repr__(self) -> str:
        return self.__str__()
