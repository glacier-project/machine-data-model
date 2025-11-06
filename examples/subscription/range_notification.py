"""
Example: Range notifications using RangeSubscription.

This demonstrates notifications on entering/exiting a specified range.
"""

from typing import Any

from machine_data_model.nodes.subscription.variable_subscription import (
    EventType,
    RangeSubscription,
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode, VariableNode


def notify_callback(
    subscription: VariableSubscription,
    node: VariableNode,
    value: Any,
) -> None:
    print(f"Notification to {subscription.subscriber_id}: {node.name} = {value}")


def main() -> None:
    # Create a numerical variable node.
    node = NumericalVariableNode(name="temperature", value=20.0)

    # RangeSubscription: notify when OUT_OF_RANGE (below 10 or above 30)
    range_sub = RangeSubscription(
        subscriber_id="range_monitor",
        correlation_id="range_alert",
        low_limit=10.0,
        high_limit=30.0,
        check_type=EventType.OUT_OF_RANGE,
    )

    node.set_subscription_callback(notify_callback)

    # Subscribe
    node.subscribe(range_sub)
    print("Subscribed to range monitor (OUT_OF_RANGE).")

    # Updates
    print("\nUpdating to 25.0 (still in range 10-30, no notify):")
    node.write(25.0)

    print("\nUpdating to 35.0 (exiting range, notify):")
    node.write(35.0)

    print("\nUpdating to 40.0 (still out, no notify):")
    node.write(40.0)

    print("\nUpdating to 15.0 (back in range, no notify for OUT_OF_RANGE):")
    node.write(15.0)

    print("\nUpdating to 5.0 (exiting range again, notify):")
    node.write(5.0)


if __name__ == "__main__":
    main()
