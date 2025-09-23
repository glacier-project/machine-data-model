"""
Example demonstrating wait condition tracing in DataModel.

This example shows how wait conditions are traced when they start waiting
for a variable to meet a condition and when the wait completes.
"""

import uuid
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.behavior.local_execution_node import (
    WaitConditionNode,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.tracing import (
    clear_traces,
    TraceLevel,
    get_global_collector,
)

# Import the utility function
from support import print_trace_events

if __name__ == "__main__":

    # Clear any previous traces
    clear_traces()

    # Create a DataModel with tracing enabled for all events
    data_model = DataModel(
        name="WaitConditionExample",
        trace_level=TraceLevel.FULL,
    )

    # Create a variable that we'll wait on
    counter_var = NumericalVariableNode(
        id="counter",
        name="counter",
        value=0,
    )

    data_model.root.add_child(counter_var)
    data_model._register_nodes(data_model.root)

    # Create a wait condition that waits for counter to be >= 5
    wait_condition = WaitConditionNode(
        variable_node="counter",
        rhs=5,
        op=WaitConditionOperator.GE,  # counter >= 5
    )
    wait_condition.set_ref_node(counter_var)

    # Create a control flow scope
    scope = ControlFlowScope(str(uuid.uuid4()))

    print("Demonstrating wait condition tracing...")
    print("Initial counter value:", counter_var.read())

    # First execution - condition not met, should start waiting
    print("\n1. Executing wait condition (counter >= 5) when counter = 0...")
    result1 = wait_condition.execute(scope)
    print(f"   Result: success={result1.success}")
    print(f"   Counter value: {counter_var.read()}")
    print(
        f"   Is scope subscribed to counter? {scope.id() in counter_var.get_subscribers()}"
    )

    # Increment counter a few times but not enough to meet condition
    print("\n2. Incrementing counter to 3 (still < 5)...")
    data_model.write_variable("counter", 3)
    print(f"   Counter value: {counter_var.read()}")

    # Execute again - still waiting
    print("\n3. Executing wait condition again (counter = 3, still < 5)...")
    result2 = wait_condition.execute(scope)
    print(f"   Result: success={result2.success}")
    print(f"   Is still subscribed? {scope.id() in counter_var.get_subscribers()}")

    # Now increment counter to meet the condition
    print("\n4. Incrementing counter to 7 (now >= 5)...")
    data_model.write_variable("counter", 7)
    print(f"   Counter value: {counter_var.read()}")

    # Execute again - condition met, should stop waiting
    print("\n5. Executing wait condition (counter = 7, now >= 5)...")
    result3 = wait_condition.execute(scope)
    print(f"   Result: success={result3.success}")
    print(f"   Is still subscribed? {scope.id() in counter_var.get_subscribers()}")

    # Display final trace events
    collector = get_global_collector()
    events = collector.get_events()
    print_trace_events(events)
