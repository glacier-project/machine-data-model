"""The default correlation id of a subscription is new for each one."""

import pytest

from machine_data_model.nodes.subscription.variable_subscription import (
    DataChangeSubscription,
    EventType,
    RangeSubscription,
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode


def make(kind: str, subscriber_id: str = "s") -> VariableSubscription:
    if kind == "base":
        return VariableSubscription(subscriber_id)
    if kind == "data_change":
        return DataChangeSubscription(subscriber_id)
    return RangeSubscription(subscriber_id, 0.0, 1.0, EventType.IN_RANGE)


KINDS = ["base", "data_change", "range"]


@pytest.mark.parametrize("kind", KINDS)
class TestDefaultId:
    def test_two_subscriptions_get_different_ids(self, kind: str) -> None:
        assert make(kind).correlation_id != make(kind).correlation_id

    def test_many_subscriptions_are_all_different(self, kind: str) -> None:
        ids = {make(kind).correlation_id for _ in range(50)}

        assert len(ids) == 50

    def test_the_id_is_a_uuid_string(self, kind: str) -> None:
        import uuid

        correlation_id = make(kind).correlation_id

        assert str(uuid.UUID(correlation_id)) == correlation_id

    def test_an_explicit_id_is_kept(self, kind: str) -> None:
        subscription: VariableSubscription
        if kind == "base":
            subscription = VariableSubscription("s", correlation_id="mine")
        elif kind == "data_change":
            subscription = DataChangeSubscription("s", correlation_id="mine")
        else:
            subscription = RangeSubscription(
                "s", 0.0, 1.0, EventType.IN_RANGE, correlation_id="mine"
            )

        assert subscription.correlation_id == "mine"

    def test_subscriptions_of_one_subscriber_are_not_equal(
        self, kind: str
    ) -> None:
        # Equality uses the subscriber and the correlation id: with a shared
        # default id every subscription of a subscriber was "equal".
        assert make(kind) != make(kind)

    def test_a_subscription_equals_itself(self, kind: str) -> None:
        subscription = make(kind)

        assert subscription == subscription

    def test_same_subscriber_and_same_explicit_id_are_equal(
        self, kind: str
    ) -> None:
        a = VariableSubscription("s", "id")
        b = VariableSubscription("s", "id")

        assert a == b


def test_positional_arguments_are_unchanged() -> None:
    callback_calls: list[object] = []

    def callback(*args: object) -> None:
        callback_calls.append(args)

    subscription = VariableSubscription("s", "corr", callback)

    assert subscription.correlation_id == "corr"
    assert subscription.subscription_callback is callback


class TestOnAVariable:
    def test_two_subscriptions_of_one_subscriber_are_both_added(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)

        assert variable.subscribe(VariableSubscription("same"))
        assert variable.subscribe(VariableSubscription("same"))

        assert len(variable.get_subscriptions()) == 2

    def test_the_same_object_is_added_once(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        subscription = VariableSubscription("same")

        assert variable.subscribe(subscription)
        assert not variable.subscribe(subscription)

        assert len(variable.get_subscriptions()) == 1

    def test_unsubscribing_one_leaves_the_other(self) -> None:
        variable = NumericalVariableNode(name="v", value=0)
        first = VariableSubscription("same")
        second = VariableSubscription("same")
        variable.subscribe(first)
        variable.subscribe(second)

        assert variable.unsubscribe(first)

        assert variable.get_subscriptions() == [second]
