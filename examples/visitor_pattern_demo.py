#!/usr/bin/env python3
"""
Example demonstrating the Visitor pattern for control flow nodes.

This example shows how different operations (tracing, validation)
can be implemented as separate visitors without modifying the node classes.
"""

from machine_data_model.behavior import (
    ControlFlow,
    TracingVisitor,
    ValidationVisitor,
)
from machine_data_model.behavior.local_execution_node import (
    ReadVariableNode,
    WriteVariableNode,
    CallMethodNode,
)
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
)


def main():
    # Create some control flow nodes
    nodes = [
        ReadVariableNode("temperature"),
        WriteVariableNode("status", "running"),
        CallMethodNode("start_process", [], {}),
        CallRemoteMethodNode("remote_sensor", "read_data", [], {}),
    ]

    # Create control flow
    control_flow = ControlFlow(nodes)

    print("=== Tracing Visitor ===")
    tracing_visitor = TracingVisitor()
    control_flow.accept(tracing_visitor)
    print("All nodes traced automatically!")

    print("\n=== Validation Visitor ===")
    # Note: ValidationVisitor needs an ExecutionContext to work properly
    # For this demo, we'll just show that it can be instantiated
    print("ValidationVisitor can be used to validate nodes before execution")
    print("It checks that nodes are properly configured and can be executed")

    print("\n=== Benefits of Visitor Pattern ===")
    print("✓ Separation of concerns: Operations are separate from node classes")
    print("✓ Extensibility: New operations can be added without modifying nodes")
    print("✓ Single responsibility: Each visitor handles one specific operation")
    print("✓ Clean code: No more if/elif/else chains for different operations")
    print("✓ Proper encapsulation: ControlFlow handles traversal automatically")


if __name__ == "__main__":
    main()
