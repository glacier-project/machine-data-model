"""
Variable node implementations for machine data models.

This module provides variable node classes that represent different types of
variables in the machine data model, including numerical, string, boolean, and
object variables with subscription and notification capabilities.
"""

from abc import abstractmethod
from collections.abc import Callable, Generator
from enum import Enum
from typing import Any

from typing_extensions import override
from unitsnet_py.abstract_unit import AbstractMeasure

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.measurement_unit.measure_builder import (
    MeasureBuilder,
    NoneMeasureUnits,
    get_measure_builder,
)
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.tracing import (
    trace_notification,
    trace_subscribe,
    trace_unsubscribe,
    trace_variable_read,
    trace_variable_write,
)


class VariableNode(DataModelNode):
    """
    A VariableNode class is a node that represents an instance of a variable in
    the machine data model. Variables of the machine data model are used to
    store the current value of a machine data or parameter.

    Attributes:
        _pre_read_value (Callable[[], None]):
            A callback function executed before reading the value.
        _post_read_value (Callable[[Any], Any]):
            A callback function executed after reading the value.
        _pre_update_value (Callable[[Any], Any]):
            A callback function executed before updating the value.
        _post_update_value (Callable[[Any, Any], bool]):
            A callback function executed after updating the value.
        _subscriptions (list[VariableSubscription]):
            A list of subscribers to the variable.
        _subscription_callback (Callable[[VariableSubscription, "VariableNode",
        Any], None]):
            A callback function that is executed to notify subscribers when an
            event occurs.

    """

    _pre_read_value: Callable[[], None]
    _post_read_value: Callable[[Any], Any]
    _pre_update_value: Callable[[Any], Any]
    _post_update_value: Callable[[Any, Any], bool]
    _subscriptions: list[VariableSubscription]
    _subscription_callback: Callable[[VariableSubscription, "VariableNode", Any], None]

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        """
        Initializes a new VariableNode instance.

        Args:
            id:
                The unique identifier of the variable.
            name:
                The name of the variable.
            description:
                The description of the variable.

        """
        super().__init__(id=id, name=name, description=description)
        # Read callbacks.
        self._pre_read_value: Callable[[], None] = lambda: None
        self._post_read_value: Callable[[Any], Any] = lambda value: value
        # Update callbacks.
        self._pre_update_value: Callable[[Any], Any] = lambda value: value
        self._post_update_value: Callable[[Any, Any], bool] = lambda prev, curr: True
        # List of subscribers and related callbacks.
        self._subscriptions: list[VariableSubscription] = []
        self._subscription_callback: Callable[
            [VariableSubscription, VariableNode, Any], None
        ] = lambda subscription, node, value: None

    def read(self) -> Any:
        """
        Get the value of the variable node.

        Returns:
            Any:
                The value of the variable node.

        """
        # Execute the pre-read callback.
        self._pre_read_value()
        # Read the actual value (method to be implemented in subclasses).
        value = self._read_value()
        # Execute the post-read callback and return the value.
        value = self._post_read_value(value)
        # Trace the variable read operation
        trace_variable_read(
            variable_id=self.id,
            value=value,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )
        # Return the read value.
        return value

    def write(self, value: Any) -> bool:
        """
        Update the value of the variable node.

        Args:
            value (Any):
                The new value of the variable node.

        Returns:
            bool:
                True if the value was updated successfully, False otherwise.

        """
        # Read the current value of the variable before the update.
        prev_value = self._read_value()
        # Apply the pre-update callback to the new value.
        value = self._pre_update_value(value)
        # Update the value of the variable with the new value.
        value = self._update_value(value)
        # Perform the post-update operations and get the success status.
        success = self._post_update_value(prev_value, value)
        # Trace the variable write operation.
        trace_variable_write(
            variable_id=self.id,
            old_value=prev_value,
            new_value=value,
            success=success,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )
        # Notify subscribers if the update was successful, otherwise restore the
        # previous value.
        if success:
            self.notify_subscribers()
        else:
            value = self._update_value(prev_value)
            assert value == prev_value
        return success

    @property
    def value(self) -> Any:
        return self.read()

    @value.setter
    def value(self, value: Any) -> None:
        self.write(value)

    def has_subscribers(self) -> bool:
        """
        Check if the variable node has subscribers.

        Returns:
            bool:
                True if the variable node has subscribers, False otherwise.

        """
        return bool(self._subscriptions)

    def get_subscriptions(self) -> list[VariableSubscription]:
        """
        Get the list of subscriptions for the variable node.

        Returns:
            list[VariableSubscription]:
                A list of subscriptions.

        """
        return self._subscriptions

    def subscribe(self, subscription: VariableSubscription) -> bool:
        """
        Subscribe a subscriber to the variable node.

        Args:
            subscription (VariableSubscription):
                The subscription to add.

        Returns:
            bool:
                True if the subscription was added successfully, False
                otherwise.

        """
        if subscription in self._subscriptions:
            return False
        # Trace the subscription operation
        trace_subscribe(
            variable_id=self.id,
            subscriber_id=subscription.subscriber_id,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )
        self._subscriptions.append(subscription)
        return True

    def _find_subscription(
        self, subscription_id: str, correlation_id: str
    ) -> VariableSubscription | None:
        """
        Find a subscription by subscriber ID and correlation ID.

        Args:
            subscription_id (str):
                The ID of the subscriber.
            correlation_id (str):
                The correlation ID of the subscription.

        Returns:
            VariableSubscription | None:
                The subscription if found, None otherwise.

        """
        for sub in self._subscriptions:
            if (
                sub.subscriber_id == subscription_id
                and sub.correlation_id == correlation_id
            ):
                return sub
        return None

    def unsubscribe(
        self,
        subscription_or_id: VariableSubscription | str,
        correlation_id: str | None = None,
    ) -> bool:
        """
        Delete a subscription from the variable node either by subscription
        object or by subscriber ID and correlation ID.

        Args:
            subscription_or_id (VariableSubscription | str):
                The subscription to remove, or the subscriber ID.
            correlation_id (str | None):
                The correlation ID when removing by IDs.

        Returns:
            bool:
                True if the subscription was removed successfully, False
                otherwise.

        Raises:
            TypeError:
                If the arguments are not of the expected types.

        """
        subscription: VariableSubscription | None
        if (
            isinstance(subscription_or_id, VariableSubscription)
            and correlation_id is None
        ):
            subscription = subscription_or_id
        elif isinstance(subscription_or_id, str) and isinstance(correlation_id, str):
            subscription = self._find_subscription(subscription_or_id, correlation_id)
        else:
            raise TypeError("unsubscribe expects (VariableSubscription) or (str, str)")

        if subscription is None or subscription not in self._subscriptions:
            return False
        # Trace the unsubscription operation
        trace_unsubscribe(
            variable_id=self.id,
            subscriber_id=subscription.subscriber_id,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )
        self._subscriptions.remove(subscription)
        return True

    def set_subscription_callback(
        self, callback: Callable[[VariableSubscription, "VariableNode", Any], None]
    ) -> None:
        """
        Set a callback to be executed when notifying subscribers.

        Args:
            callback (Callable[[VariableSubscription, "VariableNode", Any],
            None]):
                The callback to be executed when notifying subscribers.

        """
        self._subscription_callback = callback

    def notify_subscribers(self) -> None:
        """
        Notify all subscribed entities about an update or change. This will
        execute the subscription callback for each subscriber.
        """
        # Get the current value of the node.
        value = self._read_value()
        for subscription in self._subscriptions:
            if not subscription.should_notify(value):
                continue
            # Trace the notification operation.
            trace_notification(
                variable_id=self.id,
                subscriber_id=subscription.subscriber_id,
                value=value,
                source=self.qualified_name,
                data_model_id=self.data_model.name if self.data_model else "",
            )
            self._subscription_callback(subscription, self, value)

        # If the parent is a VariableNode, notify its subscribers as well.
        if isinstance(self.parent, VariableNode):
            self.parent.notify_subscribers()

    @abstractmethod
    def _read_value(self) -> Any:
        """
        Get the value of the variable.
        """

    @abstractmethod
    def _update_value(self, value: Any) -> Any:
        """
        Update the value of the variable.
        """

    def set_pre_read_value_callback(self, callback: Callable[[], None]) -> None:
        """
        Set a callback to be executed before reading the value.

        Args:
            callback (Callable[[], None]): The callback function.

        """
        self._pre_read_value = callback

    def set_post_read_value_callback(self, callback: Callable[..., Any]) -> None:
        """
        Set a callback to be executed after reading the value.

        Args:
            callback (Callable[..., Any]):
                The callback function.

        """
        self._post_read_value = callback

    def set_pre_update_value_callback(self, callback: Callable[..., Any]) -> None:
        """
        Set a callback to be executed before updating the value.

        Args:
            callback (Callable[..., Any]):
                The callback function.

        """
        self._pre_update_value = callback

    def set_post_update_value_callback(self, callback: Callable[..., bool]) -> None:
        """
        Set a callback to be executed after updating the value.

        Args:
            callback (Callable[..., bool]):
                The callback function.

        """
        self._post_update_value = callback

    def __getitem__(self, node_name: str) -> "VariableNode":
        """
        Raises an exception because child nodes are not supported.

        Args:
            node_name (str):
                The name of the node to retrieve.

        Raises:
            NotImplementedError:
                Always raised, as child nodes are not supported.

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support child nodes"
        )

    def __contains__(self, node_name: str) -> bool:
        """
        Always returns False, as this node does not have child nodes.

        Args:
            node_name (str):
                The name of the node to check.

        Returns:
            bool:
                False, as child nodes are not supported.

        """
        return False

    def __iter__(self) -> Generator["VariableNode", None, None]:
        """
        Returns an empty iterator, as this node does not have child nodes.

        Returns:
            Generator[VariableNode, None, None]:
                An empty iterator.

        """
        yield from []

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, VariableNode):
            return False

        return self._eq_base(other) and self.read() == other.read()


class NumericalVariableNode(VariableNode):
    """
    Represents an instance of a numerical variable in the machine data model.

    Attributes:
        _measure_builder (MeasureBuilder):
            A builder for creating measure objects.
        _measure_unit (Enum):
            The measure unit of the numerical variable.
        _value (AbstractMeasure):
            The value of the numerical variable, represented as an
            AbstractMeasure.

    """

    _measure_builder: MeasureBuilder = get_measure_builder()
    _value: AbstractMeasure

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        measure_unit: Enum | str = NoneMeasureUnits.NONE,
        value: float = 0,
    ):
        """
        Initializes a new NumericalVariableNode instance.

        Args:
            id (str | None):
                The unique identifier of the numerical variable.
            name (str | None):
                The name of the numerical variable.
            description (str | None):
                The description of the numerical variable.
            measure_unit (Enum | str):
                The measure unit of the numerical variable.
            value (float):
                The initial value of the numerical variable.

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

    @override
    def _read_value(self) -> float:
        """
        Get the value of the numerical variable.

        Returns:
            float:
                The value of the numerical variable.

        """
        return self._value.base_value  # type: ignore[no-any-return]

    @override
    def _update_value(self, value: float) -> float:
        """
        Update the value of the numerical variable.

        Args:
            value (float):
                The new value of the numerical variable.

        Returns:
            float:
                The updated value of the numerical variable.

        """
        self._value = self._value.__class__(value, self._measure_unit)
        return self._value.base_value  # type: ignore[no-any-return]

    def get_measure_unit(self) -> Enum:
        """
        Get the measure unit of the numerical variable.

        Returns:
            Enum:
                The measure unit of the numerical variable.

        """
        return self._measure_unit

    def __str__(self) -> str:
        """
        Returns a string representation of the NumericalVariableNode.

        Returns:
            str:
                A string describing the NumericalVariableNode.

        """
        return (
            f"NumericalVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, measure_unit={self._measure_unit}, "
            f"value={self._value})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the NumericalVariableNode for
        debugging.

        Returns:
            str:
                The string representation of the NumericalVariableNode.

        """
        return self.__str__()


class StringVariableNode(VariableNode):
    """
    Represents an instance of a string variable in the machine data model.

    Attributes:
        _value (str):
            The value of the string variable.

    """

    _value: str

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        value: str = "",
    ):
        """
        Initializes a new StringVariableNode instance.

        Args:
            id (str | None):
                The unique identifier of the string variable.
            name (str | None):
                The name of the string variable.
            description (str | None):
                The description of the string variable.
            value (str):
                The initial value of the string variable.

        """
        super().__init__(id=id, name=name, description=description)
        self._value = value

    @override
    def _read_value(self) -> str:
        """
        Get the value of the string variable.

        Returns:
            str: The value of the string variable.

        """
        return self._value

    @override
    def _update_value(self, value: str) -> str:
        """
        Update the value of the string variable.

        Args:
            value (str):
                The new value of the string variable.

        Returns:
            str:
                The updated value of the string variable.

        """
        assert isinstance(value, str)
        self._value = value
        return self._value

    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Raises a NotImplementedError, as StringVariableNode does not support
        child nodes.

        Args:
            node_name (str):
                The name of the node to retrieve.

        Raises:
            NotImplementedError:
                Always raised.

        """
        raise NotImplementedError("StringVariableNode does not support child nodes")

    def __contains__(self, node_name: str) -> bool:
        """
        Always returns False, as StringVariableNode does not support child
        nodes.

        Args:
            node_name (str):
                The name of the node to check.

        Returns:
            bool:
                False, as child nodes are not supported.

        """
        return False

    def __str__(self) -> str:
        """
        Returns a string representation of the StringVariableNode.

        Returns:
            str:
                A string describing the StringVariableNode.

        """
        return (
            f"StringVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the StringVariableNode for
        debugging.

        Returns:
            str:
                The string representation of the StringVariableNode.

        """
        return self.__str__()


class BooleanVariableNode(VariableNode):
    """
    Represents an instance of a boolean variable in the machine data model.

    Attributes:
        _value (bool):
            The value of the boolean variable.

    """

    _value: bool

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        value: bool = False,
    ):
        """
        Initializes a new BooleanVariableNode instance.

        Args:
            id (str | None):
                The unique identifier of the boolean variable.
            name (str | None):
                The name of the boolean variable.
            description (str | None):
                The description of the boolean variable.
            value (bool):
                The initial value of the boolean variable.

        """
        super().__init__(id, name, description)
        self._value = value

    @override
    def _read_value(self) -> bool:
        """
        Get the value of the boolean variable.

        Returns:
            bool:
                The value of the boolean variable.

        """
        return self._value

    @override
    def _update_value(self, value: bool) -> bool:
        """
        Update the value of the boolean variable.

        Args:
            value (bool):
                The new value of the boolean variable.

        Returns:
            bool:
                The updated value of the boolean variable.

        """
        assert isinstance(value, bool)
        self._value = value
        return self._value

    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Raises NotImplementedError as BooleanVariableNode does not support child
        nodes.

        Args:
            node_name (str):
                The name of the node.

        Raises:
            NotImplementedError:
                Always raised.

        """
        raise NotImplementedError("BooleanVariableNode does not support child nodes")

    def __contains__(self, node_name: str) -> bool:
        """
        Always returns False, as BooleanVariableNode does not support child
        nodes.

        Args:
            node_name (str):
                The name of the node.

        Returns:
            bool:
                False, as this node does not support child nodes.

        """
        return False

    def __str__(self) -> str:
        """
        Returns a string representation of the BooleanVariableNode.

        Returns:
            str:
                A string describing the BooleanVariableNode.

        """
        return (
            f"BooleanVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._value})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the BooleanVariableNode for
        debugging.

        Returns:
            str:
                The string representation of the BooleanVariableNode.

        """
        return self.__str__()


class ObjectVariableNode(VariableNode):
    """
    Represents an instance of an object variable in the machine data model.

    Attributes:
        _properties:
            A dictionary of properties of the object variable.

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

        Args:
            id (str | None):
                The unique identifier of the object variable.
            name (str | None):
                The name of the object variable.
            description (str | None):
                The description of the object variable.
            properties (dict[str, VariableNode] | None):
                The properties of the object variable.

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

        Args:
            property_node (VariableNode):
                The property node to add.

        """
        assert isinstance(
            property_node, VariableNode
        ), "Property must be a VariableNode"
        self._properties[property_node.name] = property_node
        property_node.parent = self

    def remove_property(self, property_name: str) -> None:
        """
        Remove a property from the object variable.

        Args:
            property_name (str):
                The name of the property to remove.

        """
        prop = self._properties[property_name]
        del self._properties[property_name]
        prop.parent = None

    def has_property(self, property_name: str) -> bool:
        """
        Check if the object variable has a property.

        Args:
            property_name (str):
                The name of the property to check.

        Returns:
            bool:
                True if the property exists, False otherwise.

        """
        return property_name in self._properties

    def get_property(self, property_name: str) -> VariableNode:
        """
        Get a property of the object variable.

        Args:
            property_name (str):
                The name of the property to get.

        Returns:
            VariableNode:
                The property node.

        """
        return self._properties[property_name]

    def get_properties(self) -> dict[str, VariableNode]:
        """
        Get the properties of the object variable.

        Returns:
            dict[str, VariableNode]:
                A dictionary of property nodes.

        """
        return self._properties

    def __getattr__(self, name: str) -> Any:
        """
        Get a property of the object variable using attribute access.

        Args:
            name (str):
                The name of the property to get.

        Returns:
            Any:
                The property node.

        Raises:
            AttributeError:
                If the property does not exist.

        """
        if "_properties" in self.__dict__ and name in self._properties:
            return self._properties[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    @override
    def _read_value(self) -> dict[str, Any]:
        """
        Get the value of the object variable.

        Returns:
            dict[str, Any]:
                The value of the object variable.

        """
        value = {}
        for property_name, property_node in self._properties.items():
            if isinstance(property_node, VariableNode):
                value[property_name] = property_node.read()
        return value

    @override
    def _update_value(self, value: dict[str, Any]) -> dict[str, Any]:
        """
        Update the value of the object variable.

        Args:
            value (dict[str, Any]):
                The new value of the object variable.

        Returns:
            dict[str, Any]:
                The updated value of the object variable.

        """
        assert len(value) == len(self._properties) and all(
            prop in self._properties for prop in value
        ), "The value must contain all properties of the object variable"
        for property_name, property_value in value.items():
            self._properties[property_name]._update_value(property_value)
        return self._read_value()

    def __getitem__(self, property_name: str) -> VariableNode:
        """
        Get a property of the object variable.

        Args:
            property_name (str):
                The name of the property to get.

        Returns:
            VariableNode:
                The property node.

        """
        return self.get_property(property_name)

    def __contains__(self, property_name: str) -> bool:
        """
        Check if the object variable has a property.

        Args:
            property_name (str):
                The name of the property to check.

        Returns:
            bool:
                True if the property exists, False otherwise.

        """
        return self.has_property(property_name)

    def __iter__(self) -> Generator[VariableNode, None, None]:
        """
        Iterate over the properties of the object variable.

        Returns:
            Generator[VariableNode, None, None]:
                An iterator over the properties of the object variable.

        """
        for property_node in self._properties.values():
            yield property_node

    def __str__(self) -> str:
        """
        Returns a string representation of the ObjectVariableNode.

        Returns:
            str:
                A string describing the ObjectVariableNode.

        """
        return (
            f"ObjectVariableNode(id={self._id}, name={self._name}, "
            f"description={self._description}, value={self._read_value()})"
        )

    def __repr__(self) -> str:
        """
        Returns the string representation of the ObjectVariableNode for
        debugging.

        Returns:
            str:
                The string representation of the ObjectVariableNode.

        """
        return self.__str__()
