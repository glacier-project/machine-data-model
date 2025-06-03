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

    :ivar _pre_read_value: A callback function executed before reading the value.
    :ivar _post_read_value: A callback function executed after reading the value.
    :ivar _pre_update_value: A callback function executed before updating the value.
    :ivar _post_update_value: A callback function executed after updating the value.
    :ivar _subscribers: A list of subscribers to the variable.
    :ivar _subscription_callback: A callback function that is executed to notify subscribers when an event occurs.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        connector_name: str | None = None,
    ):
        """
        Initializes a new VariableNode instance.

        :param id: The unique identifier of the variable.
        :param name: The name of the variable.
        :param description: The description of the variable.
        """
        super().__init__(
            id=id, name=name, description=description, connector_name=connector_name
        )
        # Read callbacks.
        self._pre_read_value: Callable[[], None] = lambda: None
        self._post_read_value: Callable[[Any], Any] = lambda value: value
        # Update callbacks.
        self._pre_update_value: Callable[[Any], Any] = lambda value: value
        self._post_update_value: Callable[[Any, Any], bool] = lambda prev, curr: True
        # List of subscribers and related callbacks.
        self._subscribers: list[str] = []
        self._subscription_callback: Callable[[str, "VariableNode", Any], None] = (
            lambda subscriber, node, value: None
        )

    def read(self) -> Any:
        """
        Get the value of the variable node.

        :return: The value of the variable node.
        """
        # Execute the pre-read callback.
        self._pre_read_value()
        # Read the actual value (method to be implemented in subclasses).
        value = self._read_value()
        # Execute the post-read callback and return the value.
        value = self._post_read_value(value)
        # Return the read value.
        return value

    def write(self, value: Any) -> bool:
        """
        Update the value of the variable node.

        :param value: The new value of the variable node.
        :return: True if the value was updated successfully, False otherwise.
        """
        # Read the current value of the variable before the update.
        prev_value = self._read_value()
        # Apply the pre-update callback to the new value.
        value = self._pre_update_value(value)
        # Update the value of the variable with the new value.
        value = self._update_value(value)
        # If validation fails (post-update), restore the previous value and
        # return False.
        if not self._post_update_value(prev_value, value):
            # Restore previous value if validation fails.
            self._update_value(prev_value)
            return False

        # Notify subscribers if the update was successful.
        self.notify_subscribers()

        # Return True if the value was successfully updated and validated.
        return True

    @property
    def value(self) -> Any:
        # Getter for the 'value' property
        return self.read()

    @value.setter
    def value(self, value: Any) -> None:
        # Setter for the 'value' property
        self.write(value)

    def has_subscribers(self) -> bool:
        """
        Check if the variable node has subscribers.

        :return: True if the variable node has subscribers, False otherwise.
        """
        return bool(self._subscribers)

    def get_subscribers(self) -> list[str]:
        """
        Get the list of subscribers for the variable node.

        :return: A list of subscriber IDs.
        """
        return self._subscribers

    def subscribe(self, subscriber_id: str) -> None:
        """
        Subscribe a subscriber to the variable node.

        :param subscriber_id: The ID of the subscriber.
        """
        if subscriber_id in self._subscribers:
            return
        self._subscribers.append(subscriber_id)

    def unsubscribe(self, subscriber_id: str) -> None:
        """
        Unsubscribe a subscriber from the variable node.

        :param subscriber_id: The ID of the subscriber.
        """
        if subscriber_id not in self._subscribers:
            return
        self._subscribers.remove(subscriber_id)

    def set_subscription_callback(
        self, callback: Callable[[str, "VariableNode", Any], None]
    ) -> None:
        """
        Set a callback to be executed when notifying subscribers.

        :param callback: The callback to be executed when notifying subscribers.
        """
        self._subscription_callback = callback

    def notify_subscribers(self) -> None:
        """
        Notify all subscribed entities about an update or change. This will
        execute the subscription callback for each subscriber.
        """
        # Get the current value of the node.
        value = self._read_value()
        # Pass the value to the callback.
        if isinstance(self.parent, VariableNode):
            self.parent.notify_subscribers()
        for subscriber in self._subscribers:
            self._subscription_callback(subscriber, self, value)

    def _read_value(self) -> Any:
        """
        Get the value of the variable.
        """
        # a connector could be set only after reading the full yaml file
        if self.is_remote() and self.is_connector_set():
            return self._read_remote_value()
        else:
            return self._read_internal_value()

    @abstractmethod
    def _read_internal_value(self) -> Any:
        """
        Read the value locally.
        """
        pass

    @abstractmethod
    def _read_remote_value(self) -> Any:
        """
        Read the value remotely, using the connector.
        """
        pass

    def _update_value(self, value: Any) -> Any:
        """
        Update the value of the variable.
        """
        if self.is_remote() and self.is_connector_set():
            return self._update_remote_value(value)
        else:
            return self._update_internal_value(value)

    @abstractmethod
    def _update_remote_value(self, value: Any) -> None:
        """
        Update the value of the variable remotely.

        :param value: new value
        """
        pass

    @abstractmethod
    def _update_internal_value(self, value: Any) -> None:
        """
        Update the value of the variable locally.

        :param value: new value
        """
        pass

    def set_pre_read_value_callback(self, callback: Callable[[], None]) -> None:
        """
        Set a callback to be executed before reading the value.

        :param callback: The callback function.
        """
        self._pre_read_value = callback

    def set_post_read_value_callback(self, callback: Callable[..., Any]) -> None:
        """
        Set a callback to be executed after reading the value.

        :param callback: The callback function.
        """
        self._post_read_value = callback

    def set_pre_update_value_callback(self, callback: Callable[..., Any]) -> None:
        """
        Set a callback to be executed before updating the value.

        :param callback: The callback function.
        """
        self._pre_update_value = callback

    def set_post_update_value_callback(self, callback: Callable[..., bool]) -> None:
        """
        Set a callback to be executed after updating the value.

        :param callback: The callback function.
        """
        self._post_update_value = callback

    @override
    def __getitem__(self, node_name: str) -> "VariableNode":
        """
        Raises an exception because child nodes are not supported.

        :param node_name: The name of the node to retrieve.
        :raises NotImplementedError: Always raised, as child nodes are not supported.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support child nodes"
        )

    @override
    def __contains__(self, node_name: str) -> bool:
        """
        Always returns False, as this node does not have child nodes.

        :param node_name: The name of the node to check.
        :return: False, as child nodes are not supported.
        """
        return False

    @override
    def __iter__(self) -> Iterator["VariableNode"]:
        """
        Returns an empty iterator, as this node does not have child nodes.

        :return: An empty iterator.
        """
        for _ in []:
            yield _


class NumericalVariableNode(VariableNode):
    """
    Represents an instance of a numerical variable in the machine data model.

    :ivar _measure_builder: A builder for creating measure objects.
    :ivar _measure_unit: The measure unit of the numerical variable.
    :ivar _value: The value of the numerical variable, represented as an AbstractMeasure.
    """

    _measure_builder: MeasureBuilder = get_measure_builder()

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        measure_unit: Enum | str = NoneMeasureUnits.NONE,
        value: float = 0,
        connector_name: str | None = None,
    ):
        """
        Initializes a new NumericalVariableNode instance.

        :param id: The unique identifier of the numerical variable.
        :param name: The name of the numerical variable.
        :param description: The description of the numerical variable.
        :param measure_unit: The measure unit of the numerical variable.
        :param value: The initial value of the numerical variable.
        """
        super().__init__(
            id=id, name=name, description=description, connector_name=connector_name
        )
        self._measure_unit = NumericalVariableNode._measure_builder.get_measure_unit(
            measure_unit
        )
        self._value: AbstractMeasure = (
            NumericalVariableNode._measure_builder.create_measure(
                value, self._measure_unit
            )
        )

    def _read_internal_value(self) -> float:
        """
        Get the value of the numerical variable.

        :return: The value of the numerical variable.
        """
        return self._value.base_value  # type: ignore[no-any-return]

    def _read_remote_value(self) -> float:
        """
        Get the value of the numerical variable from the remote server.

        :return: The value of the numerical variable.
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        result = self._connector.read_node_value(self.remote_path)
        assert isinstance(result, (int, float))
        return result

    def _update_internal_value(self, value: float) -> None:
        """
        Update the value of the numerical variable.

        :param value: The new value of the numerical variable.
        """
        self._value = self._value.__class__(value, self._measure_unit)

    @override
    def _update_remote_value(self, value: float) -> None:
        """
        Update the value of the numerical variable remotely.

        :param value: new value
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        self._connector.write_node_value(self.remote_path, value)

    def __str__(self) -> str:
        """
        Returns a string representation of the NumericalVariableNode.

        :return: A string describing the NumericalVariableNode.
        """
        return (
            f"NumericalVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, measure_unit={self._measure_unit}, "
            f"value={self._value})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the NumericalVariableNode for debugging.

        :return: The string representation of the NumericalVariableNode.
        """
        return self.__str__()


class StringVariableNode(VariableNode):
    """
    Represents an instance of a string variable in the machine data model.

    :ivar _value: The value of the string variable.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        value: str = "",
        connector_name: str | None = None,
    ):
        """
        Initializes a new StringVariableNode instance.

        :param id: The unique identifier of the string variable.
        :param name: The name of the string variable.
        :param description: The description of the string variable.
        :param value: The initial value of the string variable.
        """
        super().__init__(
            id=id, name=name, description=description, connector_name=connector_name
        )
        self._value: str = value

    def _read_internal_value(self) -> str:
        """
        Get the value of the string variable.

        :return: The value of the string variable.
        """
        return self._value

    @override
    def _read_remote_value(self) -> str:
        """
        Get the value of the string variable from the remote server.

        :return: The value of the string variable.
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        result = self._connector.read_node_value(self.remote_path)
        assert isinstance(result, str)
        return result

    def _update_internal_value(self, value: str) -> None:
        """
        Update the value of the string variable.

        :param value: The new value of the string variable.
        """
        assert isinstance(value, str)
        self._value = value

    @override
    def _update_remote_value(self, value: str) -> None:
        """
        Update the value of the string variable remotely.

        :param value: new value
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        self._connector.write_node_value(self.remote_path, value)

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Raises a NotImplementedError, as StringVariableNode does not support child nodes.

        :param node_name: The name of the node to retrieve.
        :raises NotImplementedError: Always raised.
        """
        raise NotImplementedError("StringVariableNode does not support child nodes")

    @override
    def __contains__(self, node_name: str) -> bool:
        """
        Always returns False, as StringVariableNode does not support child nodes.

        :param node_name: The name of the node to check.
        :return: False, as child nodes are not supported.
        """
        return False

    def __str__(self) -> str:
        """
        Returns a string representation of the StringVariableNode.

        :return: A string describing the StringVariableNode.
        """
        return (
            f"StringVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the StringVariableNode for debugging.

        :return: The string representation of the StringVariableNode.
        """
        return self.__str__()


class BooleanVariableNode(VariableNode):
    """
    Represents an instance of a boolean variable in the machine data model.

    :ivar _value: The value of the boolean variable.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        value: bool = False,
    ):
        """
        Initializes a new BooleanVariableNode instance.

        :param id: The unique identifier of the boolean variable.
        :param name: The name of the boolean variable.
        :param description: The description of the boolean variable.
        :param value: The initial value of the boolean variable.
        """
        super().__init__(id, name, description)
        self._value: bool = value

    def _read_internal_value(self) -> bool:
        """
        Get the value of the boolean variable.

        :return: The value of the boolean variable.
        """
        return self._value

    @override
    def _read_remote_value(self) -> bool:
        """
        Get the value of the boolean variable from the remote server.

        :return: The value of the boolean variable.
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        result = self._connector.read_node_value(self.remote_path)
        assert isinstance(result, bool)
        return result

    def _update_internal_value(self, value: bool) -> None:
        """
        Update the value of the boolean variable.

        :param value: The new value of the boolean variable.
        """
        assert isinstance(value, bool)
        self._value = value

    @override
    def _update_remote_value(self, value: bool) -> None:
        """
        Update the value of the boolean variable remotely.

        :param value: new value
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        self._connector.write_node_value(self.remote_path, value)

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Raises NotImplementedError as BooleanVariableNode does not support child nodes.

        :param node_name: The name of the node.
        :raises NotImplementedError: Always raised.
        """
        raise NotImplementedError("BooleanVariableNode does not support child nodes")

    @override
    def __contains__(self, node_name: str) -> bool:
        """
        Always returns False, as BooleanVariableNode does not support child nodes.

        :param node_name: The name of the node.
        :return: False, as this node does not support child nodes.
        """
        return False

    def __str__(self) -> str:
        """
        Returns a string representation of the BooleanVariableNode.

        :return: A string describing the BooleanVariableNode.
        """
        return (
            f"BooleanVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the BooleanVariableNode for debugging.

        :return: The string representation of the BooleanVariableNode.
        """
        return self.__str__()


class ObjectVariableNode(VariableNode):
    """
    Represents an instance of an object variable in the machine data model.

    :ivar _properties: A dictionary of properties of the object variable.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        properties: dict[str, VariableNode] | None = None,
    ):
        """
        Initializes a new ObjectVariableNode instance.

        :param id: The unique identifier of the object variable.
        :param name: The name of the object variable.
        :param description: The description of the object variable.
        :param properties: The properties of the object variable.
        """
        super().__init__(id=id, name=name, description=description)
        self._properties: dict[str, VariableNode] = (
            properties if properties is not None else {}
        )
        for property_node in self._properties.values():
            assert isinstance(
                property_node, VariableNode
            ), "Property must be a VariableNode"
        self.value: dict[str, Any] = self._read_value()
        self.register_children(self._properties)

    def add_property(self, property_node: VariableNode) -> None:
        """
        Add a property to the object variable.

        :param property_node: The property node to add.
        """
        assert isinstance(
            property_node, VariableNode
        ), "Property must be a VariableNode"
        self._properties[property_node.name] = property_node
        property_node.parent = self

    def remove_property(self, property_name: str) -> None:
        """
        Remove a property from the object variable.

        :param property_name: The name of the property to remove.
        """
        prop = self._properties[property_name]
        del self._properties[property_name]
        prop.parent = None

    def has_property(self, property_name: str) -> bool:
        """
        Check if the object variable has a property.

        :param property_name: The name of the property to check.
        :return: True if the property exists, False otherwise.
        """
        return property_name in self._properties

    def get_property(self, property_name: str) -> VariableNode:
        """
        Get a property of the object variable.

        :param property_name: The name of the property to get.
        :return: The property node.
        """
        return self._properties[property_name]

    def _read_internal_value(self) -> Any:
        """
        Get the value of the object variable.

        :return: The value of the object variable.
        """
        value = {}
        for property_name, property_node in self._properties.items():
            if isinstance(property_node, VariableNode):
                value[property_name] = property_node.read()
        return value

    @override
    def _read_remote_value(self) -> Any:
        """
        Get the value of the object variable from the remote server.

        :return: The value of the object variable.
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        result = self._connector.read_node_value(self.remote_path)
        return result

    def _update_internal_value(self, value: dict) -> None:
        """
        Update the value of the object variable.

        :param value: The new value of the object variable.
        """
        assert len(value) == len(self._properties) and all(
            prop in self._properties for prop in value
        ), "The value must contain all properties of the object variable"
        for property_name, property_value in value.items():
            self._properties[property_name]._update_value(property_value)

    @override
    def _update_remote_value(self, value: dict) -> None:
        """
        Update the value of the object variable remotely.

        :param value: new value
        """
        assert self._connector is not None, "Remote nodes must have a valid connector"
        assert (
            self.remote_path is not None
        ), "Remote nodes must have a valid remote path"
        self._connector.write_node_value(self.remote_path, value)

    def subscribe(self, subscriber_id: str) -> None:
        """
        Subscribe a subscriber to the variable node.

        :param subscriber_id: The ID of the subscriber.
        """
        self._subscribers.append(subscriber_id)

    def unsubscribe(self, subscriber_id: str) -> None:
        """
        Unsubscribe a subscriber from the variable node.

        :param subscriber_id: The ID of the subscriber.
        """
        self._subscribers.remove(subscriber_id)

    @override
    def notify_subscribers(self) -> None:
        """
        Notify all subscribed entities about an update or change. This will
        execute the subscription callback for each subscriber.
        """
        # Get the current value of the node.
        value = self._read_value()
        # Pass the value to the callback.
        for subscriber in self._subscribers:
            self._subscription_callback(subscriber, self, value)

    @override
    def __getitem__(self, property_name: str) -> VariableNode:
        """
        Get a property of the object variable.

        :param property_name: The name of the property to get.
        :return: The property node.
        """
        return self.get_property(property_name)

    @override
    def __contains__(self, property_name: str) -> bool:
        """
        Check if the object variable has a property.

        :param property_name: The name of the property to check.
        :return: True if the property exists, False otherwise.
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
        """
        Returns a string representation of the ObjectVariableNode.

        :return: A string describing the ObjectVariableNode.
        """
        return (
            f"ObjectVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._read_value()})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the ObjectVariableNode for debugging.

        :return: The string representation of the ObjectVariableNode.
        """
        return self.__str__()
