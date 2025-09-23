"""
Example demonstrating control flow tracing in DataModel.

This example shows how to enable FULL-level tracing to capture control flow execution,
including each step in the control flow graph with node types, execution results,
and program counter positions.
"""

import time
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.behavior.local_execution_node import (
    ReadVariableNode,
    WriteVariableNode,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.tracing import (
    clear_traces,
    TraceLevel,
    get_global_collector,
)
from support import print_trace_events


if __name__ == "__main__":

    # Clear any previous traces
    clear_traces()

    # Create a DataModel with FULL tracing enabled (includes control flow)
    data_model = DataModel(
        name="ControlFlowTracingExample",
        trace_level=TraceLevel.FULL,
    )

    # Add variables for the control flow operations
    counter_var = NumericalVariableNode(id="counter", name="counter", value=0)
    result_var = NumericalVariableNode(id="result", name="result", value=0.0)
    # Add variables to the root node.
    data_model.root.add_child(counter_var)
    data_model.root.add_child(result_var)

    # Register nodes.
    data_model._register_nodes(data_model.root)

    # Create control flow nodes
    # Node 1: Read the counter variable
    read_counter = ReadVariableNode(variable_node="counter", store_as="current_count")
    read_counter.set_ref_node(counter_var)

    # Node 2: Write a fixed value to result
    write_result = WriteVariableNode(variable_node="result", value=42.0)
    write_result.set_ref_node(result_var)

    # Node 3: Write a fixed value to counter (increment simulation)
    increment_counter = WriteVariableNode(variable_node="counter", value=5.0)
    increment_counter.set_ref_node(counter_var)

    # Create the control flow graph
    control_flow = ControlFlow([read_counter, write_result, increment_counter])

    # Simulate control flow execution multiple times
    print("Simulating control flow execution...")
    for i in range(3):
        print(f"\nExecution {i+1}:")

        # Create a new scope for each execution
        scope = ControlFlowScope(f"execution_{i+1}")

        # Execute the control flow
        messages = control_flow.execute(scope)

        # Show the results
        counter_value = data_model.read_variable("counter")
        result_value = data_model.read_variable("result")
        scope_count = scope.get_value("current_count")

        print(f"  Counter: {counter_value}")
        print(f"  Result: {result_value}")
        print(f"  Scope current_count: {scope_count}")
        print(f"  Messages sent: {len(messages)}")

        time.sleep(0.1)  # Small delay between executions

    # Display final trace events.
    collector = get_global_collector()
    events = collector.get_events()
    print_trace_events(events)
