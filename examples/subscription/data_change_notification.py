"""
Example: Data change notifications using DataChangeSubscription.

This demonstrates notifications triggered by changes exceeding a deadband.
"""

from typing import Any

from machine_data_model.nodes.subscription.variable_subscription import (
    DataChangeSubscription,
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

    # DataChangeSubscription: notify if absolute change >= 5.0
    data_sub = DataChangeSubscription(
        subscriber_id="data_monitor",
        correlation_id="change_alert",
        deadband=5.0,
    )

    node.set_subscription_callback(notify_callback)

    # Subscribe
    node.subscribe(data_sub)
    print("Subscribed to data change monitor.")

    # Updates
    print("\nUpdating to 22.0 (change: 2.0 < 5.0, no notify):")
    node.write(22.0)

    print("\nUpdating to 28.0 (change: 6.0 >= 5.0, notify):")
    node.write(28.0)

    print("\nUpdating to 30.0 (change: 2.0 < 5.0, no notify):")
    node.write(30.0)

    print("\nUpdating to 40.0 (change: 10.0 >= 5.0, notify):")
    node.write(40.0)


if __name__ == "__main__":
    main()
