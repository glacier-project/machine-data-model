"""
Example demonstrating tracing across multiple data models.

This example shows how trace events include data_model_id to distinguish
between operations in different data models, enabling debugging in
multi-model scenarios.
"""

import time

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.tracing import clear_traces, TraceLevel
from machine_data_model.tracing.tracing_core import get_global_collector, set_global_trace_level
from support import print_trace_events


def create_temperature_controller(name: str) -> DataModel:
    """Create a data model representing a temperature controller."""
    # Create DataModel with full tracing enabled
    data_model = DataModel(
        name=name,
    )

    # Add temperature sensor variable
    temp_sensor = NumericalVariableNode(
        id="temperature_sensor",
        name="temp_sensor",
        value=20.0,
    )

    # Add setpoint variable
    setpoint = NumericalVariableNode(
        id="temperature_setpoint",
        name="setpoint",
        value=22.0,
    )

    # Add a simple method to adjust temperature
    def adjust_temperature(temp_sensor: float, setpoint: float) -> float:
        """Adjust temperature towards setpoint."""
        if temp_sensor < setpoint:
            return min(temp_sensor + 2.0, setpoint)
        elif temp_sensor > setpoint:
            return max(temp_sensor - 2.0, setpoint)
        else:
            return temp_sensor

    # Create return variable
    new_temp_var = NumericalVariableNode(id="new_temp", name="new_temp", value=0.0)

    adjust_method = MethodNode(
        id="adjust_temp",
        name="adjust_temperature",
        parameters=[temp_sensor, setpoint],  # Use the actual variable nodes
        returns=[new_temp_var],
        callback=adjust_temperature,
    )

    # Add nodes to the data model
    data_model.root.add_child(temp_sensor)
    data_model.root.add_child(setpoint)
    data_model.root.add_child(adjust_method)

    # Register all nodes
    data_model._register_nodes(data_model.root)

    return data_model


if __name__ == "__main__":
    # Clear any previous traces
    clear_traces()

    # Set the tracing level to FULL to capture all events.
    set_global_trace_level(TraceLevel.FULL)

    print("Creating two temperature controller data models...")

    # Create two separate data models
    controller1 = create_temperature_controller("Controller_A")
    controller2 = create_temperature_controller("Controller_B")

    print(f"Created DataModel 1: {controller1.name} (ID: {controller1.name})")
    print(f"Created DataModel 2: {controller2.name} (ID: {controller2.name})")

    print("\nSimulating operations on both controllers...")

    # Simulate operations on Controller 1
    print("\n--- Controller A Operations ---")
    controller1.write_variable("temperature_sensor", 18.0)  # Too cold
    controller1.write_variable("temperature_setpoint", 25.0)  # Target temperature

    # Call method on Controller 1 (uses current values of parameter variables)
    result1 = controller1.call_method("adjust_temp")
    new_temp1 = result1.return_values["new_temp"]
    print(f"Controller A adjustment result: {new_temp1}")

    # Read variables from Controller 1
    temp1 = controller1.read_variable("temperature_sensor")
    setpoint1 = controller1.read_variable("temperature_setpoint")
    print(f"Controller A status: temp={temp1}, setpoint={setpoint1}")

    time.sleep(0.1)  # Small delay between controllers

    # Simulate operations on Controller 2
    print("\n--- Controller B Operations ---")
    controller2.write_variable("temperature_sensor", 28.0)  # Too hot
    controller2.write_variable("temperature_setpoint", 22.0)  # Target temperature

    # Call method on Controller 2 (uses current values of parameter variables)
    result2 = controller2.call_method("adjust_temp")
    new_temp2 = result2.return_values["new_temp"]
    print(f"Controller B adjustment result: {new_temp2}")

    # Read variables from Controller 2
    temp2 = controller2.read_variable("temperature_sensor")
    setpoint2 = controller2.read_variable("temperature_setpoint")
    print(f"Controller B status: temp={temp2}, setpoint={setpoint2}")

    # Display trace events with data model identification
    collector = get_global_collector()
    events = collector.get_events()

    print(f"\n{'='*80}")
    print("MULTI-DATA MODEL TRACING RESULTS")
    print(f"{'='*80}")
    print(f"Total events: {len(events)}")
    print(f"Controller A events: {sum(1 for e in events if e.data_model_id == 'Controller_A')}")
    print(f"Controller B events: {sum(1 for e in events if e.data_model_id == 'Controller_B')}")

    print_trace_events(events, "Multi-Data Model Trace Events")

    print("\n" + "="*80)
    print("KEY INSIGHT: Each trace event includes data_model_id to distinguish")
    print("operations across multiple data models, enabling multi-model debugging!")
    print("="*80)
