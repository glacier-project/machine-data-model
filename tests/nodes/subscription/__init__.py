import random
from machine_data_model.nodes.subscription.variable_subscription import (
    EventType,
    VariableSubscription,
    RangeSubscription,
    DataChangeSubscription,
)


def get_random_subscription(
    subscriber_id: str, correlation_id: str
) -> VariableSubscription:
    return VariableSubscription(
        subscriber_id=subscriber_id,
        correlation_id=correlation_id,
    )


def get_random_data_change_subscription(
    subscriber_id: str, correlation_id: str
) -> DataChangeSubscription:
    return DataChangeSubscription(
        subscriber_id=subscriber_id,
        correlation_id=correlation_id,
        deadband=random.uniform(0, 100),
        is_percent=random.choice([True, False]),
    )


def get_random_in_range_subscription(
    subscriber_id: str, correlation_id: str
) -> RangeSubscription:
    return RangeSubscription(
        subscriber_id=subscriber_id,
        correlation_id=correlation_id,
        check_type=EventType.IN_RANGE,
        low_limit=random.uniform(1, 50),
        high_limit=random.uniform(51, 100),
    )


def get_random_out_of_range_subscription(
    subscriber_id: str, correlation_id: str
) -> RangeSubscription:
    return RangeSubscription(
        subscriber_id=subscriber_id,
        correlation_id=correlation_id,
        check_type=EventType.OUT_OF_RANGE,
        low_limit=random.uniform(1, 50),
        high_limit=random.uniform(51, 100),
    )
