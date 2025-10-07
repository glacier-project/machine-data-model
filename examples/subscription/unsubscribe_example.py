"""
Example: Unsubscribing from a VariableNode.

This demonstrates subscribing and then unsubscribing, showing that notifications
stop.
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
    node = NumericalVariableNode(name="counter", value=0)

    # Define subscriptions
    sub1 = VariableSubscription(subscriber_id="listener1", correlation_id="corr1")
    sub2 = VariableSubscription(subscriber_id="listener2", correlation_id="corr2")

    node.set_subscription_callback(notify_callback)

    # Subscribe both
    node.subscribe(sub1)
    node.subscribe(sub2)
    print("Subscribed both listeners.")

    # Update: both should notify
    print("\nUpdating to 1:")
    node.write(1)

    # Unsubscribe sub1 by object
    node.unsubscribe(sub1)
    print("\nUnsubscribed listener1 by object.")

    # Update: only sub2 should notify
    print("\nUpdating to 2:")
    node.write(2)

    # Unsubscribe sub2 by ids
    node.unsubscribe("listener2", "corr2")
    print("\nUnsubscribed listener2 by IDs.")

    # Update: no notifications
    print("\nUpdating to 3:")
    node.write(3)
    print("No more notifications expected.")


if __name__ == "__main__":
    main()
