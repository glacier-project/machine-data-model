#!/usr/bin/env python3
"""
Message Send and Receive Tracing Example

This example demonstrates the message send and receive tracing capabilities
of the GLACIER machine data model. It shows how to trace protocol messages
at the COMMUNICATION trace level, including both incoming requests and
outgoing responses.

The example creates a protocol manager, sends various types of messages,
and demonstrates how the tracing system captures MESSAGE_SEND and MESSAGE_RECEIVE events.
"""

import json
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import FrostProtocolMng
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MsgNamespace,
    VariableMsgName,
    ProtocolMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    VariablePayload,
    ProtocolPayload,
)
from machine_data_model.tracing import (
    TraceLevel,
    export_traces_json,
    clear_traces,
    get_global_collector,
    TraceEventType,
)


def main():
    """Main example function demonstrating message send and receive tracing."""

    # Clear any existing traces
    clear_traces()

    # Create a data model with COMMUNICATION level tracing enabled
    print("Creating data model with COMMUNICATION level tracing...")
    data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)

    # Create some test variables
    temperature = NumericalVariableNode(
        id="temperature",
        name="Temperature Sensor",
        description="Room temperature in Celsius",
        value=22.5,
    )

    status = StringVariableNode(
        id="status",
        name="System Status",
        description="Current system status",
        value="online",
    )

    # Add variables to the data model
    data_model.root.add_child(temperature)
    data_model.root.add_child(status)
    data_model._register_nodes(data_model.root)

    # Create protocol manager
    print("Creating Frost protocol manager...")
    protocol_mng = FrostProtocolMng(data_model)

    print("\n=== Message Exchange Phase ===")

    # 1. Variable Read Request
    print("1. Sending variable read request...")
    read_msg = FrostMessage(
        sender="client_1",
        target="server",
        identifier="read-temp-001",
        header=FrostHeader(
            type=MsgType.REQUEST,
            version=(1, 0, 0),
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        ),
        payload=VariablePayload(node="temperature"),
    )

    response = protocol_mng.handle_request(read_msg)
    assert isinstance(response, FrostMessage)
    print(f"   Response: temperature = {response.payload.value}°C")

    # 2. Variable Write Request
    print("2. Sending variable write request...")
    write_msg = FrostMessage(
        sender="client_2",
        target="server",
        identifier="write-status-001",
        header=FrostHeader(
            type=MsgType.REQUEST,
            version=(1, 0, 0),
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.WRITE,
        ),
        payload=VariablePayload(node="status", value="maintenance"),
    )

    response = protocol_mng.handle_request(write_msg)
    assert isinstance(response, FrostMessage)
    assert isinstance(response.payload, VariablePayload)
    print(f"   Response: status updated to '{response.payload.value}'")

    # 3. Protocol Register Request
    print("3. Sending protocol register request...")
    register_msg = FrostMessage(
        sender="client_3",
        target="server",
        identifier="register-001",
        header=FrostHeader(
            type=MsgType.REQUEST,
            version=(1, 0, 0),
            namespace=MsgNamespace.PROTOCOL,
            msg_name=ProtocolMsgName.REGISTER,
        ),
        payload=ProtocolPayload(),
    )

    response = protocol_mng.handle_request(register_msg)
    print("   Response: registration acknowledged")

    # 4. Invalid Request (should generate error response)
    print("4. Sending invalid request (non-existent variable)...")
    invalid_msg = FrostMessage(
        sender="client_4",
        target="server",
        identifier="invalid-001",
        header=FrostHeader(
            type=MsgType.REQUEST,
            version=(1, 0, 0),
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        ),
        payload=VariablePayload(node="non_existent_variable"),
    )

    response = protocol_mng.handle_request(invalid_msg)
    print("   Response: error response generated")

    print("\n=== Tracing Results ===")

    # Get the global collector and display results
    collector = get_global_collector()

    # Show MESSAGE_RECEIVE events
    receive_events = collector.get_events(TraceEventType.MESSAGE_RECEIVE)
    print(f"\nMessage Receive Events ({len(receive_events)}):")
    for event in receive_events:
        details = event.details
        print(f"  - RECEIVED: {details['message_type']} from {details['sender']}")
        print(f"    Correlation ID: {details['correlation_id']}")
        print(f"    Payload: {details['payload']}")

    # Show MESSAGE_SEND events
    send_events = collector.get_events(TraceEventType.MESSAGE_SEND)
    print(f"\nMessage Send Events ({len(send_events)}):")
    for event in send_events:
        details = event.details
        print(f"  - SENT: {details['message_type']} to {details['target']}")
        print(f"    Correlation ID: {details['correlation_id']}")
        print(f"    Payload: {details['payload']}")

    # Export traces to JSON file
    print("\n=== Exporting Traces ===")
    export_traces_json("message_tracing_example.json")
    print("Traces exported to 'message_tracing_example.json'")

    # Display a summary of the JSON structure
    print("\n=== JSON Export Preview ===")
    with open("message_tracing_example.json", "r") as f:
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
    import os

    os.remove("message_tracing_example.json")
    print("Cleaned up exported trace file.")

    print("\nExample completed successfully!")
    print("\nThis example demonstrates how the tracing system captures:")
    print("- MESSAGE_RECEIVE events for all incoming protocol messages")
    print("- MESSAGE_SEND events for all outgoing responses and notifications")
    print("- Complete message metadata including type, sender, target, and payload")


if __name__ == "__main__":
    main()
