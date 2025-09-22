"""
Example demonstrating the tracing functionality in DataModel.

This example shows how to enable tracing for variable changes, reads, and method calls,
and export the trace data for analysis, similar to VCD files in hardware simulations.
"""

import os
import time
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.tracing import (
    clear_traces,
    TraceLevel,
    export_traces_json,
)


def main() -> None:
    # Clear any previous traces
    clear_traces()

    # Create a DataModel with tracing enabled for variables and methods.
    data_model = DataModel(
        name="TracingExample",
        trace_level=TraceLevel.METHODS,  # This includes VARIABLES and METHODS
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

    # Add a method that calculates something
    return_var = NumericalVariableNode(id="result", name="result", value=0.0)

    def calculate_average(temp: float, press: float) -> float:
        """Calculate a simple average of temperature and pressure."""
        return (temp + press) / 2.0

    calc_method = MethodNode(
        id="calculate_avg",
        name="calculate_average",
        parameters=[temp_var, pressure_var],
        returns=[return_var],
        callback=calculate_average,
    )

    data_model.root.add_child(calc_method)

    # Register nodes
    data_model._register_nodes(data_model.root)

    # Simulate some changes and method calls
    print("Simulating variable changes and method calls...")
    for i in range(3):
        # Update variables
        data_model.write_variable("temperature", 20.0 + i * 5.0)
        time.sleep(0.1)  # Small delay for different timestamps
        data_model.write_variable("pressure", 1.0 + i * 0.1)

        # Read the variables
        temp_value = data_model.read_variable("temperature")
        pressure_value = data_model.read_variable("pressure")
        print(f"  Read: temperature={temp_value}, pressure={pressure_value}")

        # Call the method
        result = data_model.call_method("calculate_avg")
        avg_value = result.return_values["result"]
        print(f"  Method result: average={avg_value}")

    # Export the trace.
    trace_file = "simulation_trace.json"
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


if __name__ == "__main__":
    main()
