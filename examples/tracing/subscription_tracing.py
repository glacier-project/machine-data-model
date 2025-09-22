#!/usr/bin/env python3
"""
Subscription and Notification Tracing Example

This example demonstrates the subscription and notification tracing capabilities
of the GLACIER machine data model. It shows how to trace variable subscriptions,
unsubscriptions, and notifications at the COMMUNICATION trace level.

The example creates variables, subscribes to them, writes values to trigger
notifications, and demonstrates how the tracing system captures these events.
"""

import json
import os
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.tracing import (
    TraceLevel,
    export_traces_json,
    clear_traces,
    get_global_collector,
    TraceEventType,
)


def notification_callback(subscriber_id: str, variable_node, value):
    """
    Example callback function for subscription notifications.

    :param subscriber_id: The ID of the subscriber receiving the notification.
    :param variable_node: The variable node that changed.
    :param value: The new value of the variable.
    """
    print(f"Subscriber {subscriber_id} notified: {variable_node.name} = {value}")


if __name__ == "__main__":

    # Clear any existing traces
    clear_traces()

    # Create a data model with COMMUNICATION level tracing enabled
    print("Creating data model with COMMUNICATION level tracing...")
    data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)

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
    temperature.subscribe("thermostat_controller")
    temperature.subscribe("monitoring_system")
    temperature.subscribe("alert_system")

    # Subscribe to humidity as well
    print("Subscribing monitoring system to humidity variable...")
    humidity.subscribe("monitoring_system")

    print("\n=== Setting Up Callbacks ===")

    # Set up notification callbacks
    temperature.set_subscription_callback(notification_callback)
    humidity.set_subscription_callback(notification_callback)

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
    temperature.unsubscribe("alert_system")

    # Update temperature again - alert_system should not be notified
    print("Updating temperature to 26.0°C (alert_system should not be notified)...")
    data_model.write_variable("temperature", 26.0)

    print("\n=== Tracing Results ===")

    # Get the global collector and display results
    collector = get_global_collector()

    # Show subscription events
    subscribe_events = collector.get_events(TraceEventType.SUBSCRIBE)
    print(f"\nSubscription Events ({len(subscribe_events)}):")
    for event in subscribe_events:
        details = event.details
        print(f"  - {details['subscriber_id']} subscribed to {details['variable_id']}")

    # Show unsubscription events
    unsubscribe_events = collector.get_events(TraceEventType.UNSUBSCRIBE)
    print(f"\nUnsubscription Events ({len(unsubscribe_events)}):")
    for event in unsubscribe_events:
        details = event.details
        print(
            f"  - {details['subscriber_id']} unsubscribed from {details['variable_id']}"
        )

    # Show notification events
    notification_events = collector.get_events(TraceEventType.NOTIFICATION)
    print(f"\nNotification Events ({len(notification_events)}):")
    for event in notification_events:
        details = event.details
        print(
            f"  - {details['subscriber_id']} notified: {details['variable_id']} = {details['value']}"
        )

    # Export traces to JSON file
    print("\n=== Exporting Traces ===")
    export_traces_json("subscription_tracing_example.json")
    print("Traces exported to 'subscription_tracing_example.json'")

    # Display a summary of the JSON structure
    print("\n=== JSON Export Preview ===")
    with open("subscription_tracing_example.json", "r") as f:
        traces = json.load(f)

    # Group events by type for summary
    event_summary = {}
    for trace in traces:
        event_type = trace["event_type"]
        if event_type not in event_summary:
            event_summary[event_type] = 0
        event_summary[event_type] += 1

    print("Event Summary:")
    for event_type, count in event_summary.items():
        print(f"  {event_type}: {count} events")

    # Clean up the exported file
    os.remove("subscription_tracing_example.json")
    print("Cleaned up exported trace file.")

    print("\nExample completed successfully!")
