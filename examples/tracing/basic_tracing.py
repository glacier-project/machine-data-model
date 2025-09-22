"""
Example demonstrating basic variable tracing in DataModel.

This example shows how to enable tracing for variable changes and reads,
and export the trace data for analysis, similar to VCD files in hardware simulations.
"""

import os
import time
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.tracing import (
    clear_traces,
    TraceLevel,
    export_traces_json,
)


if __name__ == "__main__":

    # Clear any previous traces
    clear_traces()

    # Create a DataModel with tracing enabled for variables.
    data_model = DataModel(
        name="VariableTracingExample",
        trace_level=TraceLevel.VARIABLES,  # Enable variable tracing only
    )

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

    # Export the trace.
    trace_file = "variable_trace.json"
    export_traces_json(trace_file)
    print(f"Trace exported to {trace_file}")

    # Verify the file was created and show some stats
    if os.path.exists(trace_file):
        file_size = os.path.getsize(trace_file)
        print(f"Trace file size: {file_size} bytes")

        print("Sample trace data:")
        with open(trace_file, "r") as f:
            data = f.read(1000)
            print(data + "...\n")

        # Clean up
        os.remove(trace_file)
        print(f"Cleaned up {trace_file}")
    else:
        print(f"Warning: {trace_file} was not created")
