"""
Example demonstrating basic variable tracing in DataModel.

This example shows how to enable tracing for variable changes and reads,
and export the trace data for analysis, similar to VCD files in hardware simulations.
"""

import time

from support import print_trace_events

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.tracing import TraceLevel, clear_traces
from machine_data_model.tracing.tracing_core import (
    get_global_collector,
    set_global_trace_level,
)


def main() -> None:

    # Clear any previous traces
    clear_traces()

    # Set the tracing level to FULL to capture all events.
    set_global_trace_level(TraceLevel.FULL)

    # Create a DataModel with tracing enabled for variables.
    data_model = DataModel(name="VariableTracingExample")

    # Add some variables
    temp_var = NumericalVariableNode(
        id="temperature",
        name="temp",
        value=20.0,
    )
    pressure_var = NumericalVariableNode(
        id="pressure",
        name="press",
        value=1.0,
    )

    data_model.root.add_child(temp_var)
    data_model.root.add_child(pressure_var)

    # Register nodes
    data_model._register_nodes(data_model.root)

    # Simulate some variable changes and reads
    print("Simulating variable changes and reads...")
    for i in range(3):
        # Update variables
        data_model.write_variable("temperature", 20.0 + i * 5.0)
        time.sleep(0.1)  # Small delay for different timestamps
        data_model.write_variable("pressure", 1.0 + i * 0.1)

        # Read the variables
        temp_value = data_model.read_variable("temperature")
        pressure_value = data_model.read_variable("pressure")
        print(f"  Read: temperature={temp_value}, pressure={pressure_value}")

    # Display final trace events
    collector = get_global_collector()
    events = collector.get_events()
    print_trace_events(events)

if __name__ == "__main__":
    main()
