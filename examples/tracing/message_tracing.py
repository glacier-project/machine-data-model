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

from support import print_trace_events

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgNamespace,
    MsgType,
    ProtocolMsgName,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    ProtocolPayload,
    VariablePayload,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import FrostProtocolMng
from machine_data_model.tracing import (
    TraceLevel,
    clear_traces,
    get_global_collector,
    set_global_trace_level,
)


def main() -> None:

    # Clear any existing traces
    clear_traces()

    # Set the tracing level to FULL to capture all events.
    set_global_trace_level(TraceLevel.FULL)

    # Create a data model with COMMUNICATION level tracing enabled
    print("Creating data model with COMMUNICATION level tracing...")
    data_model = DataModel("MessageTracingExample")

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
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        ),
        payload=VariablePayload(node="temperature"),
    )

    response = protocol_mng.handle_request(read_msg)
    assert isinstance(response, FrostMessage)
    assert isinstance(response.payload, VariablePayload)
    print(f"   Response: temperature = {response.payload.value}°C")

    # 2. Variable Write Request
    print("2. Sending variable write request...")
    write_msg = FrostMessage(
        sender="client_2",
        target="server",
        identifier="write-status-001",
        header=FrostHeader(
            type=MsgType.REQUEST,
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
            namespace=MsgNamespace.VARIABLE,
            msg_name=VariableMsgName.READ,
        ),
        payload=VariablePayload(node="non_existent_variable"),
    )

    response = protocol_mng.handle_request(invalid_msg)
    print("   Response: error response generated")

    # Display final trace events.
    collector = get_global_collector()
    events = collector.get_events()
    print_trace_events(events)


if __name__ == "__main__":
    main()
