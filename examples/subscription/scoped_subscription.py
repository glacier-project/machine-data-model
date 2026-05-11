"""Example: Multiple scoped subscription callbacks inside a small data model.

This demonstrates a small hierarchical data model, then attaches a subscription
callback directly to the subscription object at runtime.
"""

from typing import Any

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    VariableNode,
)


def print_model(folder: FolderNode, indent: int = 0) -> None:
    """Print a folder tree with current variable values."""
    prefix = " " * indent
    print(f"{prefix}- {folder.name}")
    for child in folder:
        if isinstance(child, FolderNode):
            print_model(child, indent + 2)
        elif isinstance(child, NumericalVariableNode):
            print(f"{prefix}  - {child.name} = {child.read()}")
        else:
            print(f"{prefix}  - {child.name} ({type(child).__name__})")


def subscription_callback(
    subscription: VariableSubscription,
    node: VariableNode,
    value: Any,
) -> None:
    """Print a notification when the subscription fires."""
    print(f"  {subscription.subscriber_id} saw {node.name} -> {value}")


def main() -> None:
    """Run the scoped subscription example."""
    data_model = DataModel(
        name="SubscriptionExample",
        description="Small model for demonstrating scoped subscriptions",
    )

    machine = FolderNode(name="machine", description="Demo machine")
    sensors = FolderNode(name="sensors", description="Sensor values")
    actuators = FolderNode(name="actuators", description="Actuator values")

    temperature = NumericalVariableNode(name="temperature", value=20.0)
    pressure = NumericalVariableNode(name="pressure", value=1.0)
    fan_speed = NumericalVariableNode(name="fan_speed", value=1000.0)

    sensors.add_child(temperature)
    sensors.add_child(pressure)
    actuators.add_child(fan_speed)
    machine.add_child(sensors)
    machine.add_child(actuators)
    data_model.root.add_child(machine)

    data_model._register_nodes(data_model.root)

    print("Data model layout:")
    print_model(data_model.root)

    subscription_a = VariableSubscription(
        subscriber_id="listener_1",
        correlation_id="temperature_scope",
        subscription_callback=subscription_callback,
    )

    subscription_b = VariableSubscription(
        subscriber_id="listener_2",
        correlation_id="temperature_scope_b",
        subscription_callback=subscription_callback,
    )

    temperature_path = temperature.qualified_name
    if data_model.subscribe(temperature_path, subscription_a):
        print(f"Subscribed 1 listener at runtime to {temperature_path}")

    pressure_path = pressure.qualified_name
    if data_model.subscribe(pressure_path, subscription_b):
        print(f"Subscribed 1 listener at runtime to {pressure_path}")

    print("\nUpdating temperature to 25.0")
    data_model.write_variable(temperature_path, 25.0)

    print("\nUpdating pressure to 1.2")
    data_model.write_variable(pressure_path, 1.2)


if __name__ == "__main__":
    main()
