from enum import IntFlag, auto
from typing import Any
from typing_extensions import override
from uuid import uuid4


class EventType(IntFlag):
    """Enumeration of possible event types for variable subscriptions."""

    DATA_CHANGE = auto()
    OUT_OF_RANGE = auto()
    IN_RANGE = auto()
    ANY = auto()


class VariableSubscription:
    """Base class for variable subscriptions. It represents a subscription to any change.

    :ivar subscriber_id: Identifier of the subscriber.
    :ivar correlation_id: Correlation identifier for the subscription.
    """

    def __init__(self, subscriber_id: str, correlation_id: str = str(uuid4())):
        self.subscriber_id = subscriber_id
        self.correlation_id = correlation_id

    def get_event_type(self) -> EventType:
        """Get the event types this subscription is interested in."""
        return EventType.ANY

    def should_notify(self, new_value: Any) -> bool:
        """Determine if a notification should be sent based on the new value.

        :param new_value: The new value of the variable.
        :return: True if a notification should be sent, False otherwise.
        """
        return True

    def __eq__(self, other: object) -> bool:
        if other is self:
            return True
        if not isinstance(other, VariableSubscription):
            return False
        return (
            self.subscriber_id == other.subscriber_id
            and self.correlation_id == other.correlation_id
        )

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}(subscriber_id={self.subscriber_id}, "
            f"correlation_id={self.correlation_id})"
        )

    def __repr__(self) -> str:
        return str(self)


class DataChangeSubscription(VariableSubscription):
    """Subscription for data change events. It notifies when the variable's value changes beyond a specified deadband.

    :ivar deadband: Minimum change required to trigger a notification.
    :ivar is_percent: If True, deadband is treated as a percentage of the
    previous value; otherwise, it's an absolute value.
    :ivar _previous_value: The last known value of the variable.
    """

    def __init__(
        self,
        subscriber_id: str,
        correlation_id: str,
        deadband: float = 0.0,
        is_percent: bool = False,
    ):
        super().__init__(subscriber_id, correlation_id)
        self._previous_value: None | float = None
        self.deadband = deadband
        self.is_percent = is_percent

    @override
    def get_event_type(self) -> EventType:
        return EventType.DATA_CHANGE

    def _value_changed(self, new_value: float) -> bool:
        previous_value = self._previous_value
        deadband = self.deadband
        is_percent = self.is_percent

        if previous_value is None:
            return True
        if is_percent and previous_value != 0:
            change = abs((new_value - previous_value) / previous_value) * 100
        else:
            change = abs(new_value - previous_value)
        return change >= deadband

    @override
    def should_notify(self, new_value: float) -> bool:
        value_changed = self._value_changed(new_value)

        if value_changed:
            self._previous_value = new_value
        return value_changed


class RangeSubscription(VariableSubscription):
    """Subscription for range-based events. It notifies when the variable's value enters or exits a specified range.

    :ivar low_limit: Lower bound of the range.
    :ivar high_limit: Upper bound of the range.
    :ivar _check_type: Type of range check (IN_RANGE or OUT_OF_RANGE).
    """

    def __init__(
        self,
        subscriber_id: str,
        correlation_id: str,
        low_limit: float,
        high_limit: float,
        check_type: EventType,
    ):
        super().__init__(subscriber_id, correlation_id)
        self.low_limit = low_limit
        self.high_limit = high_limit

        if check_type not in (EventType.IN_RANGE, EventType.OUT_OF_RANGE):
            raise ValueError("check_type must be either IN_RANGE or OUT_OF_RANGE")
        self._check_type = check_type

    @override
    def get_event_type(self) -> EventType:
        return self._check_type

    @override
    def should_notify(self, new_value: float) -> bool:
        if self._check_type == EventType.IN_RANGE:
            return self.low_limit <= new_value <= self.high_limit
        return new_value < self.low_limit or new_value > self.high_limit
