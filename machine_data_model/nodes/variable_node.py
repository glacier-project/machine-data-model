"""Variable node implementations for machine data models.

This module provides variable node classes that represent different types of
variables in the machine data model, including numerical, string, boolean, and
object variables with subscription and notification capabilities.
"""

from abc import abstractmethod
from collections.abc import Callable, Generator
from enum import Enum
import logging
from typing import Any
import warnings

from typing_extensions import override
from unitsnet_py.abstract_unit import AbstractMeasure

from machine_data_model.nodes.connectors.abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)
from machine_data_model.tracing import (
    trace_notification,
    trace_subscribe,
    trace_unsubscribe,
    trace_variable_read,
    trace_variable_write,
)

from .connectors.abstract_connector import (
    AbstractConnector,
    SubscriptionArguments,
)
from .connectors.remote_resource import RemoteResource
from .data_model_node import DataModelNode
from .measurement_unit.measure_builder import (
    MeasureBuilder,
    NoneMeasureUnits,
    get_measure_builder,
)
from .subscription.variable_subscription import (
    VariableSubscription,
)

_logger = logging.getLogger(__name__)

# Hooks that earlier versions called and that no longer exist: a subclass that
# still overrides one of them is silently ignored, so warn about it.
_REMOVED_HOOKS = {
    "_update_remote_value": "implement _write_remote(value) -> bool",
    "_update_value": "implement _write_remote(value) -> bool",
    "_read_remote_value": "the raw remote value comes from "
    "_fetch_remote_value()",
}


class VariableNode(DataModelNode):
    """Represent an instance of a variable in the machine data model.

    Variables of the machine data model are used to store the current value of
    a machine data or parameter.

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
    _subscription_callback: Callable[
        [VariableSubscription, "VariableNode", Any], None
    ]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Warn about overrides of hooks that were removed.

        Args:
            **kwargs (Any):
                Class keyword arguments, passed on.

        """
        super().__init_subclass__(**kwargs)
        for hook, advice in _REMOVED_HOOKS.items():
            if hook in cls.__dict__:
                # Level 3: ABCMeta.__new__ sits between the class statement of
                # the subclass and this hook.
                warnings.warn(
                    f"{cls.__qualname__} defines {hook}(), which was removed "
                    f"and is never called; {advice}",
                    DeprecationWarning,
                    stacklevel=3,
                )

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ):
        """Initializes a new VariableNode instance.

        Args:
            id:
                The unique identifier of the variable.
            name:
                The name of the variable.
            description:
                The description of the variable.
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (RemoteResourceSpec | None):
                Protocol-specific properties for the remote resource.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
        )
        # Read callbacks.
        self._pre_read_value: Callable[[], None] = lambda: None
        self._post_read_value: Callable[[Any], Any] = lambda value: value
        # Update callbacks.
        self._pre_update_value: Callable[[Any], Any] = lambda value: value
        self._post_update_value: Callable[[Any, Any], bool] = (
            lambda prev, curr: True
        )
        # List of subscribers and related callbacks.
        self._subscriptions: list[VariableSubscription] = []
        self._subscription_callback: Callable[
            [VariableSubscription, VariableNode, Any], None
        ] = lambda subscription, node, value: None

    def read(self, force_remote_read: bool = True) -> Any:
        """Get the value of the variable node.

        Args:
            force_remote_read (bool, optional):
                If True, when the variable is a remote variable, use the
                connector to read the remote value. If false, return the cached
                value. Default is True.

        Returns:
            Any:
                The value of the variable node.

        """
        # Execute the pre-read callback.
        self._pre_read_value()
        # Read the actual value (method to be implemented in subclasses).
        value = self._read_value(force_remote_read=force_remote_read)
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
        """Update the value of the variable node.

        Args:
            value (Any):
                The new value of the variable node.

        Returns:
            bool:
                True if the value was updated successfully, False otherwise.

        """
        # Read the current value of the variable before the update, and keep a
        # snapshot of its state to restore it exactly if the update is rejected.
        prev_value = self._read_value()
        snapshot = self._snapshot()
        # Apply the pre-update callback to the new value.
        value = self._pre_update_value(value)
        remote = self._is_remote_with_connector()
        # For a remote variable the remote write comes first and the cache only
        # changes if the connector confirmed it. Success is never inferred from
        # comparing values: the cache can hold a converted (base unit) value.
        if remote and not self._write_remote(value):
            trace_variable_write(
                variable_id=self.id,
                old_value=prev_value,
                new_value=value,
                success=False,
                source=self.qualified_name,
                data_model_id=self.data_model.name if self.data_model else "",
            )
            return False
        # Update the cached value of the variable with the new value.
        value = self._update_internal_value(value)
        # Perform the post-update operations and get the success status. For a
        # remote variable this runs AFTER the machine was written: validators
        # belong in `_pre_update_value`.
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
        elif remote and not self._write_remote(self._remote_value(snapshot)):
            # The restore is a second remote write and can fail too: the
            # machine keeps the new value, so does the cache.
            _logger.error(
                "Failed to restore the previous value of '%s' on the remote "
                "server after a rejected update",
                self.qualified_name,
            )
        else:
            self._restore(snapshot)
        return success

    @property
    def value(self) -> Any:
        """Return the current value of the variable."""
        return self.read()

    @value.setter
    def value(self, value: Any) -> None:
        self.write(value)

    def has_subscribers(self) -> bool:
        """Check if the variable node has subscribers.

        Returns:
            bool:
                True if the variable node has subscribers, False otherwise.

        """
        return bool(self._subscriptions)

    def get_subscriptions(self) -> list[VariableSubscription]:
        """Get the list of subscriptions for the variable node.

        Returns:
            list[VariableSubscription]:
                A list of subscriptions.

        """
        return self._subscriptions

    def find_subscription_by_subscriber(
        self, subscriber_id: str
    ) -> VariableSubscription | None:
        """Find the first subscription of a subscriber.

        Args:
            subscriber_id (str):
                The id of the subscriber.

        Returns:
            VariableSubscription | None:
                The subscription, or None if the subscriber has none.

        """
        for subscription in self._subscriptions:
            if subscription.subscriber_id == subscriber_id:
                return subscription
        return None

    def subscribe(self, subscription: VariableSubscription) -> bool:
        """Subscribe a subscriber to the variable node.

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
        """Find a subscription by subscriber ID and correlation ID.

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
        """Unsubscribe a subscriber from the variable node.

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
        elif isinstance(subscription_or_id, str) and isinstance(
            correlation_id, str
        ):
            subscription = self._find_subscription(
                subscription_or_id, correlation_id
            )
        else:
            raise TypeError(
                "unsubscribe expects (VariableSubscription) or (str, str)"
            )

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
        self,
        callback: Callable[[VariableSubscription, "VariableNode", Any], None],
    ) -> None:
        """Set a callback to be executed when notifying subscribers.

        Args:
            callback:
                The callback to be executed when notifying subscribers.

        """
        self._subscription_callback = callback

    def notify_subscribers(self) -> None:
        """Notify all subscribed entities about an update or change.

        Iterates through all subscriptions and triggers notifications based on
        the variable's current value. When subscription criteria are met, the
        subscription callback is invoked (if set), otherwise the node
        subscription callback is used. This process recursively propagates to
        the parent if it is a `VariableNode`.
        """
        # Get the current value of the node.
        value = self._read_internal_value()
        # Iterate over a copy: a callback can resume a context that
        # unsubscribes, which mutates the live list and would skip a waiter.
        for subscription in list(self._subscriptions):
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

            if subscription.subscription_callback is not None:
                subscription.notify(self, value)
            else:
                self._subscription_callback(subscription, self, value)

        # If the parent is a VariableNode, notify its subscribers as well.
        if isinstance(self.parent, VariableNode):
            self.parent.notify_subscribers()

    def _read_value(self, force_remote_read: bool = False) -> Any:
        """Get the value of the variable.

        Args:
            force_remote_read (bool, optional):
                If True, when the variable is a remote variable, use the
                connector to read the remote value. If False, return the cached
                value. Default is False.

        Returns:
            Any:
                Variable's value.
        """
        # a connector could be set only after reading the full yaml file
        if self.is_remote() and self.has_connector():
            # The cache is only written when a value really came from the
            # connector. Feeding the cached (base unit) value back through
            # `_update_internal_value` would convert it again on every read.
            # A forced read returns the connector value as it always did (in
            # the unit of the variable, see issue #67); a cached read returns
            # the cache untouched.
            if force_remote_read:
                value = self._fetch_remote_value()
                if value is not None:
                    self._update_internal_value(value)
                    return value
            return self._read_internal_value()
        else:
            return self._read_internal_value()

    def _fetch_remote_value(self) -> Any:
        """Read the raw value from the remote server.

        Returns:
            Any:
                The value as sent by the connector (in the unit of the
                variable), or None if the server has no value.

        """
        connector = self._require_remote_connector()
        return connector.read_node_value(self._require_remote_resource())

    def _require_remote_connector(self) -> AbstractConnector:
        """Return the connector or fail with a runtime exception."""
        if self._connector is None:
            raise RuntimeError("Remote nodes must have a valid connector")
        return self._connector

    def _require_remote_resource(self) -> RemoteResource:
        """Return the configured remote resource or fail clearly."""
        try:
            return self.remote_resource
        except ValueError as exp:
            raise ValueError(
                "Remote nodes must have a valid remote path or resource spec"
            ) from exp

    @abstractmethod
    def _read_internal_value(self) -> Any:
        """Read the value locally.

        Returns:
            Any:
                Variable's internal value.
        """

    def _snapshot(self) -> Any:
        """Capture the state of the variable so that it can be restored.

        Returns:
            Any:
                An opaque snapshot, to be passed to `_restore` and
                `_remote_value`.

        """
        return self._read_internal_value()

    def _restore(self, snapshot: Any) -> None:
        """Restore the cache from a snapshot, exactly.

        Args:
            snapshot (Any):
                A snapshot taken by `_snapshot`.

        """
        self._update_internal_value(snapshot)

    def _remote_value(self, snapshot: Any) -> Any:
        """Return the value to send to the remote server for a snapshot.

        Args:
            snapshot (Any):
                A snapshot taken by `_snapshot`.

        Returns:
            Any:
                The value in the form the machine expects (the unit of the
                variable), which is what it held before the update.

        """
        return snapshot

    def _is_remote_with_connector(self) -> bool:
        """Whether writes go through a connector."""
        return self.is_remote() and self.has_connector()

    def _write_remote(self, value: Any) -> bool:
        """Write the value to the remote server.

        Args:
            value (Any):
                The value to write.

        Returns:
            bool:
                True only if the connector confirmed the write.

        """
        connector = self._require_remote_connector()
        return bool(
            connector.write_node_value(self._require_remote_resource(), value)
        )

    @abstractmethod
    def _update_internal_value(self, value: Any) -> Any:
        """Update the value of the variable locally.

        Args:
            value:
                New value.

        Returns:
            Any:
                New updated value.
        """
        pass

    def set_pre_read_value_callback(self, callback: Callable[[], None]) -> None:
        """Set a callback to be executed before reading the value.

        Args:
            callback (Callable[[], None]): The callback function.

        """
        self._pre_read_value = callback

    def set_post_read_value_callback(
        self, callback: Callable[..., Any]
    ) -> None:
        """Set a callback to be executed after reading the value.

        Args:
            callback (Callable[..., Any]):
                The callback function.

        """
        self._post_read_value = callback

    def set_pre_update_value_callback(
        self, callback: Callable[..., Any]
    ) -> None:
        """Set a callback to be executed before updating the value.

        Args:
            callback (Callable[..., Any]):
                The callback function.

        """
        self._pre_update_value = callback

    def set_post_update_value_callback(
        self, callback: Callable[..., bool]
    ) -> None:
        """Set a callback to be executed after updating the value.

        The callback receives the previous and the new value and returns False
        to reject the update, which then restores the previous value. For a
        remote variable it runs AFTER the machine was written, so the restore
        is a second remote write that can fail (the failure is logged and the
        cache keeps the new value). Validators belong in the pre-update
        callback.

        Args:
            callback (Callable[..., bool]):
                The callback function.

        """
        self._post_update_value = callback

    def subscribe_to_remote_changes(self) -> None:
        """Subscribe to remote variable changes using the connector.

        When the new value is retrieved, calls the _remote_subscription_callback
        which updates the internal cached value.
        """
        connector = self.connector
        if connector is None or not (
            self._remote_path or self._remote_resource_spec
        ):
            return None
        resource = self.remote_resource
        connector.subscribe_to_node_changes(
            resource,
            self._remote_subscription_callback,
        )
        value = connector.read_node_value(resource)
        if value is not None:
            self._update_internal_value(value)
        return None

    def _remote_subscription_callback(
        self, value: Any, _other: SubscriptionArguments
    ) -> None:
        """Handle remote variable changes by updating the internal cached value.

        Args:
            value (Any):
                Value that was read from remote.
            _other (SubscriptionArguments):
                Protocol-specific data that is available from the remote
                subscription.
        """
        self._update_internal_value(value)
        self.notify_subscribers()

    def __getitem__(self, node_name: str) -> "VariableNode":
        """Raises an exception because child nodes are not supported.

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
        """Always returns False, as this node does not have child nodes.

        Args:
            node_name (str):
                The name of the node to check.

        Returns:
            bool:
                False, as child nodes are not supported.

        """
        return False

    def __iter__(self) -> Generator["VariableNode", None, None]:
        """Returns an empty iterator, as this node does not have child nodes.

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
    """Represents an instance of a numerical variable in the machine data model.

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
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ):
        """Initializes a new NumericalVariableNode instance.

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
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (RemoteResourceSpec | None):
                Properties that are specific to the connector/protocol.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
        )
        self._measure_unit = (
            NumericalVariableNode._measure_builder.get_measure_unit(
                measure_unit
            )
        )
        self._value: AbstractMeasure = (
            NumericalVariableNode._measure_builder.create_measure(
                value, self._measure_unit
            )
        )

    @override
    def _read_internal_value(self) -> float:
        """Get the value of the numerical variable.

        Returns:
            float:
                The value of the numerical variable.

        """
        return self._value.base_value  # type: ignore[no-any-return]

    @override
    def _update_internal_value(self, value: float) -> float:
        """Update the value of the numerical variable.

        Args:
            value (float):
                The new value of the numerical variable.

        Returns:
            float:
                The updated value of the numerical variable.

        """
        self._value = self._value.__class__(value, self._measure_unit)
        return self._value.base_value  # type: ignore[no-any-return]

    @override
    def _snapshot(self) -> AbstractMeasure:
        """Capture the measure (value and unit) of the variable.

        The measure is replaced, never mutated, by an update, so keeping the
        reference is a faithful snapshot.

        Returns:
            AbstractMeasure:
                The current measure.

        """
        return self._value

    @override
    def _restore(self, snapshot: AbstractMeasure) -> None:
        """Restore the exact measure captured by `_snapshot`.

        Args:
            snapshot (AbstractMeasure):
                The measure to restore.

        """
        self._value = snapshot

    @override
    def _remote_value(self, snapshot: AbstractMeasure) -> float:
        """Return the snapshot in the unit of the variable.

        Args:
            snapshot (AbstractMeasure):
                The measure captured by `_snapshot`.

        Returns:
            float:
                The value in the unit of the variable, as the machine had it.

        """
        if self._measure_unit == NoneMeasureUnits.NONE:
            return snapshot.base_value  # type: ignore[no-any-return]
        return snapshot.convert(self._measure_unit)  # type: ignore[no-any-return]

    def get_measure_unit(self) -> Enum:
        """Get the measure unit of the numerical variable.

        Returns:
            Enum:
                The measure unit of the numerical variable.

        """
        return self._measure_unit

    def __str__(self) -> str:
        """Returns a string representation of the NumericalVariableNode.

        Returns:
            str:
                A string describing the NumericalVariableNode.

        """
        return (
            f"NumericalVariableNode(id={self._id}, "
            f"name={self._name}, "
            f"description={self._description}, "
            f"measure_unit={self._measure_unit}, "
            f"value={self._read_internal_value()!r})"
        )

    def __repr__(self) -> str:
        """Return the string representation of the NumericalVariableNode.

        Returns:
            str:
                The string representation of the NumericalVariableNode.

        """
        return self.__str__()


class StringVariableNode(VariableNode):
    """Represents an instance of a string variable in the machine data model.

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
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ):
        """Initializes a new StringVariableNode instance.

        Args:
            id (str | None):
                The unique identifier of the string variable.
            name (str | None):
                The name of the string variable.
            description (str | None):
                The description of the string variable.
            value (str):
                The initial value of the string variable.
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (RemoteResourceSpec | None):
                Properties that are specific to the connector/protocol.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
        )
        self._value = value

    @override
    def _read_internal_value(self) -> str:
        """Get the value of the string variable.

        Returns:
            str: The value of the string variable.

        """
        return self._value

    @override
    def _update_internal_value(self, value: str) -> str:
        """Update the value of the string variable.

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
        """Raise NotImplementedError.

        StringVariableNode does not support children.

        Args:
            node_name (str):
                The name of the node to retrieve.

        Raises:
            NotImplementedError:
                Always raised.

        """
        raise NotImplementedError(
            "StringVariableNode does not support child nodes"
        )

    def __contains__(self, node_name: str) -> bool:
        """Return False as StringVariableNode does not support child nodes.

        Args:
            node_name (str):
                The name of the node to check.

        Returns:
            bool:
                False, as child nodes are not supported.

        """
        return False

    def __str__(self) -> str:
        """Returns a string representation of the StringVariableNode.

        Returns:
            str:
                A string describing the StringVariableNode.

        """
        return (
            f"StringVariableNode(id={self._id}, "
            f"name={self._name}, "
            f"description={self._description}, "
            f"value={self._read_internal_value()!r})"
        )

    def __repr__(self) -> str:
        """Return the string representation of the StringVariableNode.

        Returns:
            str:
                The string representation of the StringVariableNode.

        """
        return self.__str__()


class BooleanVariableNode(VariableNode):
    """Represents an instance of a boolean variable in the machine data model.

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
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ):
        """Initializes a new BooleanVariableNode instance.

        Args:
            id (str | None):
                The unique identifier of the boolean variable.
            name (str | None):
                The name of the boolean variable.
            description (str | None):
                The description of the boolean variable.
            value (bool):
                The initial value of the boolean variable.
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (RemoteResourceSpec | None):
                Properties that are specific to the connector/protocol.
        """
        super().__init__(
            id,
            name,
            description,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
        )
        self._value = value

    @override
    def _read_internal_value(self) -> bool:
        """Get the value of the boolean variable.

        Returns:
            bool:
                The value of the boolean variable.

        """
        return self._value

    @override
    def _update_internal_value(self, value: bool) -> bool:
        """Update the value of the boolean variable.

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
        """Raise NotImplementedError.

        BooleanVariableNode does not support children.

        Args:
            node_name (str):
                The name of the node.

        Raises:
            NotImplementedError:
                Always raised.

        """
        raise NotImplementedError(
            "BooleanVariableNode does not support child nodes"
        )

    def __contains__(self, node_name: str) -> bool:
        """Return False as BooleanVariableNode does not support child nodes.

        Args:
            node_name (str):
                The name of the node.

        Returns:
            bool:
                False, as this node does not support child nodes.

        """
        return False

    def __str__(self) -> str:
        """Returns a string representation of the BooleanVariableNode.

        Returns:
            str:
                A string describing the BooleanVariableNode.

        """
        return (
            f"BooleanVariableNode(id={self._id}, "
            f"name={self._name}, "
            f"description={self._description}, "
            f"value={self._read_internal_value()!r})"
        )

    def __repr__(self) -> str:
        """Return the string representation of the BooleanVariableNode.

        Returns:
            str:
                The string representation of the BooleanVariableNode.

        """
        return self.__str__()


class ObjectVariableNode(VariableNode):
    """Represents an instance of an object variable in the machine data model.

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
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
    ):
        """Initializes a new ObjectVariableNode instance.

        Args:
            id (str | None):
                The unique identifier of the object variable.
            name (str | None):
                The name of the object variable.
            description (str | None):
                The description of the object variable.
            properties (dict[str, VariableNode] | None):
                The properties of the object variable.
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (RemoteResourceSpec | None):
                Properties that are specific to the connector/protocol.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
        )
        self._properties: dict[str, VariableNode] = (
            properties if properties is not None else {}
        )
        for property_node in self._properties.values():
            assert isinstance(
                property_node, VariableNode
            ), "Property must be a VariableNode"
        self.value: dict[str, Any] = self._read_internal_value()
        self.register_children(self._properties)

    def add_property(self, property_node: VariableNode) -> None:
        """Add a property to the object variable.

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
        """Remove a property from the object variable.

        Args:
            property_name (str):
                The name of the property to remove.

        """
        prop = self._properties[property_name]
        del self._properties[property_name]
        prop.parent = None

    def has_property(self, property_name: str) -> bool:
        """Check if the object variable has a property.

        Args:
            property_name (str):
                The name of the property to check.

        Returns:
            bool:
                True if the property exists, False otherwise.

        """
        return property_name in self._properties

    def get_property(self, property_name: str) -> VariableNode:
        """Get a property of the object variable.

        Args:
            property_name (str):
                The name of the property to get.

        Returns:
            VariableNode:
                The property node.

        """
        return self._properties[property_name]

    def get_properties(self) -> dict[str, VariableNode]:
        """Get the properties of the object variable.

        Returns:
            dict[str, VariableNode]:
                A dictionary of property nodes.

        """
        return self._properties

    def __getattr__(self, name: str) -> Any:
        """Get a property of the object variable using attribute access.

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
    def _read_internal_value(self) -> dict[str, Any]:
        """Get the value of the object variable.

        Returns:
            dict[str, Any]:
                The value of the object variable.

        """
        value = {}
        for property_name, property_node in self._properties.items():
            if isinstance(property_node, VariableNode):
                value[property_name] = property_node._read_internal_value()
        return value

    @override
    def _read_value(self, force_remote_read: bool = False) -> Any:
        """Get the value of the object variable.

        A forced read of a remote object reads each property through its own
        forced read (each one writes its own cache only when it really received
        a value) and returns the values as they were returned, so the result
        has the same domain as the property reads.

        Args:
            force_remote_read (bool, optional):
                If True, refresh the properties from the remote server.

        Returns:
            Any:
                The value of the object variable.
        """
        if self.is_remote() and self.has_connector():
            self._require_remote_resource()
            if force_remote_read:
                return {
                    name: property_node._read_value(force_remote_read=True)
                    for name, property_node in self._properties.items()
                }
        return self._read_internal_value()

    @override
    def _update_internal_value(self, value: dict[str, Any]) -> dict[str, Any]:
        """Update the value of the object variable.

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
            self._properties[property_name]._update_internal_value(
                property_value
            )
        return self._read_internal_value()

    @override
    def _snapshot(self) -> dict[str, Any]:
        """Capture the state of every property.

        Returns:
            dict[str, Any]:
                The snapshot of each property, by name.

        """
        return {
            name: node._snapshot() for name, node in self._properties.items()
        }

    @override
    def _restore(self, snapshot: dict[str, Any]) -> None:
        """Restore every property from its snapshot.

        Args:
            snapshot (dict[str, Any]):
                The snapshot captured by `_snapshot`.

        """
        for name, property_snapshot in snapshot.items():
            self._properties[name]._restore(property_snapshot)

    @override
    def _remote_value(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Return every property snapshot in the unit of the property.

        Args:
            snapshot (dict[str, Any]):
                The snapshot captured by `_snapshot`.

        Returns:
            dict[str, Any]:
                The value to send to the remote server, by property name.

        """
        return {
            name: self._properties[name]._remote_value(property_snapshot)
            for name, property_snapshot in snapshot.items()
        }

    @override
    def _write_remote(self, value: dict[str, Any]) -> bool:
        """Write the properties of the object variable to the remote server.

        All the properties must be given: this is checked before the machine is
        touched. If a property write is not confirmed, or raises, only the
        properties that were confirmed are rolled back, in reverse order, to
        the value (in the unit of the property) they had before. A rollback
        that fails is logged with the names of the properties left unrestored.

        Args:
            value (dict[str, Any]):
                The new value of the object variable.

        Returns:
            bool:
                True only if every property write was confirmed.

        Raises:
            ValueError:
                If the value does not contain exactly the properties of the
                object.

        """
        self._require_remote_connector()
        self._require_remote_resource()
        if set(value) != set(self._properties):
            missing = sorted(set(self._properties) - set(value))
            unknown = sorted(set(value) - set(self._properties))
            raise ValueError(
                f"cannot write '{self.qualified_name}': missing properties "
                f"{missing}, unknown properties {unknown}"
            )
        before = {
            name: node._remote_value(node._snapshot())
            for name, node in self._properties.items()
        }
        written: list[str] = []
        try:
            for property_name, property_value in value.items():
                if not self._properties[property_name]._write_remote(
                    property_value
                ):
                    self._roll_back(written, before)
                    return False
                written.append(property_name)
        except Exception:
            self._roll_back(written, before)
            raise
        return True

    def _roll_back(self, written: list[str], before: dict[str, Any]) -> None:
        """Restore the confirmed properties on the remote server.

        Args:
            written (list[str]):
                The names of the properties whose write was confirmed.
            before (dict[str, Any]):
                The previous value of every property, in its own unit.

        """
        unrestored: list[str] = []
        for property_name in reversed(written):
            try:
                restored = self._properties[property_name]._write_remote(
                    before[property_name]
                )
            except Exception:
                _logger.exception(
                    "Rollback of property '%s' of '%s' raised",
                    property_name,
                    self.qualified_name,
                )
                restored = False
            if not restored:
                unrestored.append(property_name)
        if unrestored:
            _logger.error(
                "Failed to roll back properties %s of '%s': the machine keeps "
                "their new values",
                unrestored,
                self.qualified_name,
            )

    def __getitem__(self, property_name: str) -> VariableNode:
        """Get a property of the object variable.

        Args:
            property_name (str):
                The name of the property to get.

        Returns:
            VariableNode:
                The property node.

        """
        return self.get_property(property_name)

    def __contains__(self, property_name: str) -> bool:
        """Check if the object variable has a property.

        Args:
            property_name (str):
                The name of the property to check.

        Returns:
            bool:
                True if the property exists, False otherwise.

        """
        return self.has_property(property_name)

    def __iter__(self) -> Generator[VariableNode, None, None]:
        """Iterate over the properties of the object variable.

        Returns:
            Generator[VariableNode, None, None]:
                An iterator over the properties of the object variable.

        """
        yield from self._properties.values()

    def __str__(self) -> str:
        """Returns a string representation of the ObjectVariableNode.

        Returns:
            str:
                A string describing the ObjectVariableNode.

        """
        return (
            f"ObjectVariableNode(id={self._id}, "
            f"name={self._name}, "
            f"description={self._description}, "
            f"value={self._read_internal_value()})"
        )

    def __repr__(self) -> str:
        """Return the string representation of the ObjectVariableNode.

        Returns:
            str:
                The string representation of the ObjectVariableNode.

        """
        return self.__str__()


class InternalVariableNode(VariableNode):
    """Marker class for variable nodes internal to a composite method.

    Internal variable nodes are not accessible from external clients and are
    only accessible within the control flow of the composite method that
    contains them.

    This class doesn't add any functionality beyond the base VariableNode,
    but serves as a marker for internal use.
    """

    pass
