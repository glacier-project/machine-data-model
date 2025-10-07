"""
Example: Basic subscription and notification for a NumericalVariableNode.

This demonstrates subscribing to a variable, updating its value, and receiving
notifications.
"""

from typing import Any
from machine_data_model.nodes.variable_node import NumericalVariableNode, VariableNode
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)


def notify_callback(
    subscription: VariableSubscription,
    node: VariableNode,
    value: Any,
) -> None:
    print(f"Notification to {subscription.subscriber_id}: {node.name} = {value}")


def main() -> None:
    # Create a numerical variable node.
    node = NumericalVariableNode(name="temperature", value=20.0)

    # Define a simple subscription.
    subscription = VariableSubscription(
        subscriber_id="sensor1", correlation_id="temp_monitor"
    )

    node.set_subscription_callback(notify_callback)

    # Subscribe and update the value.
    node.subscribe(subscription)
    print(f"Subscribed: {subscription}")
    success = node.write(25.0)  # Should trigger notification.
    print(f"Update successful: {success}")


if __name__ == "__main__":
    main()
