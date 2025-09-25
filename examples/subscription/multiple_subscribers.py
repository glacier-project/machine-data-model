"""
Example: Multiple subscribers to the same VariableNode.

This demonstrates handling multiple subscriptions on a single node.
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
    node = NumericalVariableNode(name="shared_value", value=0)

    # Define multiple subscriptions
    subs = [
        VariableSubscription(subscriber_id="sub1", correlation_id="c1"),
        VariableSubscription(subscriber_id="sub2", correlation_id="c2"),
        VariableSubscription(subscriber_id="sub3", correlation_id="c3"),
    ]

    node.set_subscription_callback(notify_callback)

    # Subscribe all
    for sub in subs:
        node.subscribe(sub)
    print("Subscribed 3 listeners.")

    # Update: all should notify
    print("\nUpdating to 10:")
    node.write(10)

    # Unsubscribe one
    node.unsubscribe(subs[1])
    print("\nUnsubscribed sub2.")

    # Update: only two should notify
    print("\nUpdating to 20:")
    node.write(20)


if __name__ == "__main__":
    main()
