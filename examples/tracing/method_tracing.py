"""
Example demonstrating method execution tracing in DataModel.

This example shows how to enable tracing for method calls and their execution,
including start/end times and return values.
"""

import time
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.tracing import (
    clear_traces,
    TraceLevel,
)


if __name__ == "__main__":

    # Clear any previous traces
    clear_traces()

    # Create a DataModel with tracing enabled for methods.
    data_model = DataModel(
        name="MethodTracingExample",
        trace_level=TraceLevel.METHODS,  # This includes VARIABLES and METHODS
    )

    # Add some variables that will be used as parameters
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

    # Simulate method calls with different parameters
    print("Simulating method calls...")
    for i in range(3):
        # Update variables first (these will also be traced)
        data_model.write_variable("temperature", 20.0 + i * 5.0)
        time.sleep(0.1)  # Small delay for different timestamps
        data_model.write_variable("pressure", 1.0 + i * 0.1)

        # Call the method
        result = data_model.call_method("calculate_avg")
        avg_value = result.return_values["result"]
        print(f"  Method call {i+1}: average={avg_value}")
