#!/usr/bin/env python3
"""
Subscription and Notification Tracing Example

This example demonstrates the subscription and notification tracing capabilities
of the GLACIER machine data model. It shows how to trace variable subscriptions,
unsubscriptions, and notifications at the COMMUNICATION trace level.

The example creates variables, subscribes to them, writes values to trigger
notifications, and demonstrates how the tracing system captures these events.
"""

from typing import Any

from support import print_trace_events

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode, VariableNode
from machine_data_model.tracing import (
    TraceLevel,
    clear_traces,
    get_global_collector,
)
from machine_data_model.tracing.tracing_core import set_global_trace_level


def notify_callback(
    subscription: VariableSubscription,
    node: VariableNode,
    value: Any,
) -> None:
    print(f"Notification to {subscription.subscriber_id}: {node.name} = {value}")


def main() -> None:

    # Clear any existing traces
    clear_traces()

    # Set the tracing level to FULL to capture all events.
    set_global_trace_level(TraceLevel.FULL)

    # Create a data model with COMMUNICATION level tracing enabled
    print("Creating data model with COMMUNICATION level tracing...")
    data_model = DataModel("SubscriptionTracingExample")

    # Create some numerical variables
    temperature = NumericalVariableNode(
        id="temperature",
        name="Temperature Sensor",
        description="Room temperature in Celsius",
        value=22.5,
    )

    humidity = NumericalVariableNode(
        id="humidity",
        name="Humidity Sensor",
        description="Room humidity percentage",
        value=65.0,
    )

    # Add variables to the data model
    data_model.root.add_child(temperature)
    data_model.root.add_child(humidity)
    data_model._register_nodes(data_model.root)

    print("\n=== Subscription Phase ===")

    # Subscribe multiple entities to the temperature variable
    print("Subscribing entities to temperature variable...")
    temperature.subscribe(VariableSubscription("thermostat_controller", "corr_1"))
    temperature.subscribe(VariableSubscription("monitoring_system", "corr_2"))
    temperature.subscribe(VariableSubscription("alert_system", "corr_3"))

    # Subscribe to humidity as well
    print("Subscribing monitoring system to humidity variable...")
    humidity.subscribe(VariableSubscription("monitoring_system", "corr_4"))

    print("\n=== Setting Up Callbacks ===")

    # Set up notification callbacks
    temperature.set_subscription_callback(notify_callback)
    humidity.set_subscription_callback(notify_callback)

    print("\n=== Value Update Phase ===")

    # Update temperature - this should trigger notifications to all subscribers
    print("Updating temperature to 25.0°C...")
    data_model.write_variable("temperature", 25.0)

    # Update humidity - this should trigger notification to monitoring system only
    print("Updating humidity to 70.0%...")
    data_model.write_variable("humidity", 70.0)

    # Update temperature again
    print("Updating temperature to 23.5°C...")
    data_model.write_variable("temperature", 23.5)

    print("\n=== Unsubscription Phase ===")

    # Unsubscribe one entity from temperature
    print("Unsubscribing alert_system from temperature...")
    temperature.unsubscribe(VariableSubscription("alert_system", "corr_3"))

    # Update temperature again - alert_system should not be notified
    print("Updating temperature to 26.0°C (alert_system should not be notified)...")
    data_model.write_variable("temperature", 26.0)

    print("\n=== Tracing Results ===")

    # Display final trace events
    collector = get_global_collector()
    events = collector.get_events()
    print_trace_events(events)


if __name__ == "__main__":
    main()
