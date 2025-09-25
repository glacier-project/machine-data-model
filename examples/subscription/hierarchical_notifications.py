"""
Example: Hierarchical notifications in ObjectVariableNode.

This demonstrates how notifications propagate from child properties to parent
objects.
"""

from typing import Any
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    ObjectVariableNode,
    VariableNode,
)
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
    # Create an object variable node
    obj_node = ObjectVariableNode(name="sensor_data")

    # Add a numerical property
    temp_prop = NumericalVariableNode(name="temperature", value=20.0)
    obj_node.add_property(temp_prop)

    # Subscribe to the object node
    obj_sub = VariableSubscription(
        subscriber_id="object_monitor",
        correlation_id="obj_corr",
    )

    obj_node.set_subscription_callback(notify_callback)

    # Subscribe to object
    obj_node.subscribe(obj_sub)
    print("Subscribed to object node.")

    # Update the property: should trigger notification on object
    print("\nUpdating temperature property to 25.0:")
    temp_prop.write(25.0)

    # Also subscribe to the property directly
    prop_sub = VariableSubscription(
        subscriber_id="prop_monitor", correlation_id="prop_corr"
    )
    temp_prop.set_subscription_callback(notify_callback)
    temp_prop.subscribe(prop_sub)
    print("\nSubscribed to property directly.")

    # Update property again: both should notify
    print("\nUpdating temperature property to 30.0:")
    temp_prop.write(30.0)


if __name__ == "__main__":
    main()
