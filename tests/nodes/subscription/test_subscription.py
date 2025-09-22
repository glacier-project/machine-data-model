import pytest
import random
from typing import Any
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
    DataChangeSubscription,
    EventType,
    RangeSubscription,
)
from tests import NUM_TESTS, gen_random_simple_value, gen_random_float, gen_random_bool


class TestSubscription:
    @pytest.mark.parametrize(
        "value", [gen_random_simple_value() for _ in range(NUM_TESTS)]
    )
    def test_base_subscription(self, value: Any) -> None:
        subscription = VariableSubscription("subscriber_1", "corr_1")

        assert subscription.subscriber_id == "subscriber_1"
        assert subscription.correlation_id == "corr_1"
        assert subscription.should_notify(value)
        assert subscription.get_event_type() == EventType.ANY

    @pytest.mark.parametrize("values", [[gen_random_float() for _ in range(NUM_TESTS)]])
    def test_data_change_subscription(self, values: list[float]) -> None:
        subscription = DataChangeSubscription("subscriber_1", "corr_1")

        assert subscription.get_event_type() == EventType.DATA_CHANGE
        prev_value = None
        for value in values:
            assert subscription.should_notify(value) == (
                prev_value is None or value != prev_value
            )
            prev_value = value

    @pytest.mark.parametrize(
        "value, deadband",
        [(gen_random_float(), gen_random_float()) for _ in range(NUM_TESTS)],
    )
    def test_data_change_deadband(self, value: float, deadband: float) -> None:
        subscription = DataChangeSubscription(
            "subscriber_1", "corr_1", deadband=deadband
        )

        expected_notifications = [True] + [gen_random_bool() for _ in range(NUM_TESTS)]
        test_values = [value]
        last_notify_idx = 0
        for i, notify in enumerate(expected_notifications[1:]):
            if notify:
                test_values.append(
                    test_values[last_notify_idx]
                    + (deadband * gen_random_float(1.0, 2.0)) * random.choice([-1, 1])
                )
                last_notify_idx = i + 1
            else:
                test_values.append(
                    test_values[last_notify_idx]
                    + (deadband * gen_random_float(0.0, 0.99)) * random.choice([-1, 1])
                )

        assert subscription.subscriber_id == "subscriber_1"
        assert subscription.correlation_id == "corr_1"
        assert subscription.get_event_type() == EventType.DATA_CHANGE
        assert subscription.deadband == deadband
        assert not subscription.is_percent
        for value, expected in zip(test_values, expected_notifications):
            assert subscription.should_notify(value) == expected

    @pytest.mark.parametrize(
        "value, deadband",
        [(gen_random_float(), gen_random_float(1, 20)) for _ in range(NUM_TESTS)],
    )
    def test_data_change_percent_deadband(self, value: float, deadband: float) -> None:
        subscription = DataChangeSubscription(
            "subscriber_1", "corr_1", deadband=deadband, is_percent=True
        )

        expected_notifications = [True] + [gen_random_bool() for _ in range(NUM_TESTS)]
        test_values = [value]
        last_notify_idx = 0
        for i, notify in enumerate(expected_notifications[1:]):
            if notify:
                change = (
                    (deadband / 100.0)
                    * test_values[last_notify_idx]
                    * gen_random_float(1.0, 2.0)
                )
                test_values.append(
                    test_values[last_notify_idx] + change * random.choice([-1, 1])
                )
                last_notify_idx = i + 1
            else:
                change = (
                    (deadband / 100.0)
                    * test_values[last_notify_idx]
                    * gen_random_float(0.0, 0.99)
                )
                test_values.append(
                    test_values[last_notify_idx] + change * random.choice([-1, 1])
                )

        assert subscription.subscriber_id == "subscriber_1"
        assert subscription.correlation_id == "corr_1"
        assert subscription.get_event_type() == EventType.DATA_CHANGE
        assert subscription.deadband == deadband
        assert subscription.is_percent
        for value, expected in zip(test_values, expected_notifications):
            assert subscription.should_notify(value) == expected

    @pytest.mark.parametrize(
        "values, low_limit, high_limit",
        [
            (
                [gen_random_float(0, 100) for _ in range(NUM_TESTS)],
                gen_random_float(1, 50),
                gen_random_float(51, 100),
            )
        ],
    )
    @pytest.mark.parametrize("check_type", [EventType.IN_RANGE, EventType.OUT_OF_RANGE])
    def test_subscription_range(
        self,
        values: list[float],
        low_limit: float,
        high_limit: float,
        check_type: EventType,
    ) -> None:
        subscription = RangeSubscription(
            "subscriber_1",
            "corr_1",
            low_limit=low_limit,
            high_limit=high_limit,
            check_type=check_type,
        )

        for value in values:
            in_range = low_limit <= value <= high_limit
            if check_type == EventType.IN_RANGE:
                should_notify = in_range
            else:
                should_notify = not in_range

            assert subscription.should_notify(value) == should_notify
