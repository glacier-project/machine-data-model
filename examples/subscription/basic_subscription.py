"""Example: Basic subscription and notification for a NumericalVariableNode.

This demonstrates subscribing to a variable, updating its value, and receiving
notifications.
"""

from typing import Any

from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    VariableNode,
)


def notify_callback(
    subscription: VariableSubscription,
    node: VariableNode,
    value: Any,
) -> None:
    """Callback to notify subscriber of variable change.

    Args:
        subscription (VariableSubscription):
            The subscription information.
        node (VariableNode):
            The variable node that changed.
        value (Any):
            The new value of the variable.

    """
    print(
        f"Notification to {subscription.subscriber_id}: {node.name} = {value}"
    )


def main() -> None:
    """Basic subscription example."""
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
