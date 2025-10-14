"""
Simple example of distributed tracing: local machine reads temperature from remote machine.
This version uses multiprocessing to simulate truly separate entities.
"""

import atexit
import multiprocessing
import time
from typing import Any

from support import print_trace_events

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.local_execution_node import WriteVariableNode
from machine_data_model.behavior.remote_execution_node import ReadRemoteVariableNode
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgNamespace,
    MsgType,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    FrostPayload,
    VariablePayload,
)
from machine_data_model.tracing import TraceLevel, clear_traces, get_global_collector
from machine_data_model.tracing.tracing_core import set_global_trace_level


def cleanup_process(machine_name: str) -> None:
    """
    Cleanup function called when a process terminates.

    Args:
        machine_name (str, optional):
            Name of the machine ("RemoteMachine" or "LocalMachine").
            Defaults to "RemoteMachine".

    """
    print(f"\n=== {machine_name} cleanup ===")
    collector = get_global_collector()
    events = collector.get_events()
    if events:
        print_trace_events(events, f"Trace Events from {machine_name}")
    else:
        print(f"No trace events from {machine_name}")
    print(f"=== {machine_name} cleanup complete ===")


def serialize_frost_message(msg: FrostMessage) -> dict[str, Any]:
    """Serialize a FrostMessage for inter-process communication."""
    from machine_data_model.protocols.frost_v1.frost_payload import VariablePayload

    payload_data = None
    if isinstance(msg.payload, VariablePayload):
        payload_data = {
            "node": msg.payload.node,
            "value": msg.payload.value,
        }

    return {
        "correlation_id": msg.correlation_id,
        "sender": msg.sender,
        "target": msg.target,
        "header": {
            "type": msg.header.type.value,
            "version": msg.header.version,
            "namespace": msg.header.namespace.value,
            "msg_name": msg.header.msg_name.value,
        },
        "payload": payload_data,
    }


def deserialize_frost_message(data: dict[str, Any]) -> FrostMessage:
    """Deserialize a FrostMessage from inter-process communication."""
    header = FrostHeader(
        type=MsgType(data["header"]["type"]),
        version=tuple(data["header"]["version"]),
        namespace=MsgNamespace(data["header"]["namespace"]),
        msg_name=VariableMsgName(data["header"]["msg_name"]),
    )

    payload = None
    if data["payload"] is not None:
        payload = VariablePayload(
            node=data["payload"]["node"],
            value=data["payload"]["value"],
        )

    return FrostMessage(
        correlation_id=data["correlation_id"],
        sender=data["sender"],
        target=data["target"],
        header=header,
        payload=payload if payload is not None else FrostPayload(),
    )


def remote_machine_process(
    request_queue: multiprocessing.Queue, response_queue: multiprocessing.Queue
) -> None:
    """Process function for the remote machine."""
    # Register cleanup function
    atexit.register(lambda: cleanup_process("RemoteMachine"))

    # Clear any existing traces.
    clear_traces()

    # Set the tracing level to FULL to capture all events.
    set_global_trace_level(TraceLevel.FULL)

    INIT_TEMP = 25.5

    # Initialize remote machine
    remote_machine = DataModel(name="RemoteMachine")
    remote_temp = NumericalVariableNode(
        id="temperature",
        name="temperature",
        value=INIT_TEMP,
    )
    remote_machine.root.add_child(remote_temp)
    remote_machine._register_nodes(remote_machine.root)

    def machine_log(msg: str) -> None:
        print(f"[RemoteMachine] {msg}")

    machine_log(f"Initialized with temperature: {INIT_TEMP}")

    # Process requests
    while True:
        try:
            # Check for exit signal
            if not request_queue.empty():
                request_data = request_queue.get_nowait()

                # Check if this is an exit signal
                if isinstance(request_data, dict) and request_data.get("exit"):
                    machine_log("Exit!")
                    break

                request_msg = deserialize_frost_message(request_data)

                machine_log(f"Received request for: {request_msg.payload.node}")

                # Process the request
                var_name = request_msg.payload.node
                try:
                    value = remote_machine.read_variable(var_name)
                    machine_log(f"Read {var_name} = {value}")
                except Exception as e:
                    value = None
                    machine_log(f"Error reading {var_name}: {e}")

                # Create response
                response_msg = FrostMessage(
                    correlation_id=request_msg.correlation_id,
                    sender=request_msg.target,  # Remote machine
                    target=request_msg.sender,  # Local machine
                    header=FrostHeader(
                        type=MsgType.RESPONSE,
                        version=(1, 0, 0),
                        namespace=MsgNamespace.VARIABLE,
                        msg_name=VariableMsgName.READ,
                    ),
                    payload=VariablePayload(node=var_name, value=value),
                )

                # Send response
                response_data = serialize_frost_message(response_msg)
                response_queue.put(response_data)
                machine_log(f"Sent response for {var_name}")

            time.sleep(0.01)  # Small delay to prevent busy waiting

        except Exception as e:
            machine_log(f"Error: {e}")
            break


def local_machine_process(
    request_queue: multiprocessing.Queue,
    response_queue: multiprocessing.Queue,
    result_dict: dict[str, Any],
) -> None:
    """Process function for the local machine."""
    # Register cleanup function
    atexit.register(lambda: cleanup_process("LocalMachine"))

    # Clear any existing traces.
    clear_traces()

    # Set the tracing level to FULL to capture all events.
    set_global_trace_level(TraceLevel.FULL)

    INIT_TEMP = 0.0

    def machine_log(msg: str) -> None:
        print(f"[LocalMachine ] {msg}")

    try:
        # Initialize local machine
        local_machine = DataModel(name="LocalMachine")
        local_temp = NumericalVariableNode(
            id="local_temp",
            name="local_temp",
            value=INIT_TEMP,
        )
        composite_method = CompositeMethodNode(
            id="temp_sync_method",
            name="Temperature Sync Method",
        )
        local_machine.root.add_child(local_temp)
        local_machine.root.add_child(composite_method)
        local_machine._register_nodes(local_machine.root)

        machine_log(f"Initialized with temperature: {INIT_TEMP}")

        # Control flow: read remote temperature, store locally
        read_remote_temp = ReadRemoteVariableNode(
            variable_node="temperature",
            remote_id="RemoteMachine",
            store_as="local_temp",
        )

        write_local_temp = WriteVariableNode(
            variable_node="local_temp",
            value="$local_temp",
        )
        write_local_temp.set_ref_node(local_temp)

        control_flow = ControlFlow(
            [
                read_remote_temp,
                write_local_temp,
            ],
            composite_method_node=composite_method,
        )

        # Execute: Phase 1 - Send request
        machine_log("Starting control flow execution")
        context = ExecutionContext("temp_sync")
        messages = control_flow.execute(context)

        machine_log(f"Sent {len(messages)} messages")

        # Send request to remote machine
        if messages:
            request_data = serialize_frost_message(messages[0])
            request_queue.put(request_data)
            machine_log(f"Sent request for {messages[0].payload.node}")

        # Wait for response
        response_received = False
        max_wait_time = 5.0  # 5 seconds timeout
        start_time = time.time()

        while not response_received and (time.time() - start_time) < max_wait_time:
            if not response_queue.empty():
                response_data = response_queue.get_nowait()
                response_msg = deserialize_frost_message(response_data)

                machine_log(f"Received response for {response_msg.payload.node}")

                # Handle the response.
                handled = read_remote_temp.handle_response(context, response_msg)
                machine_log(f"Response handled: {handled}")
                response_received = True

            time.sleep(0.01)  # Small delay

        if not response_received:
            machine_log("Timeout waiting for response")
            result_dict["error"] = "Timeout waiting for response"
            return

        # Execute: Phase 2 - Process response and write locally
        machine_log("Processing response and writing locally")
        messages2 = control_flow.execute(context)
        machine_log(f"Sent {len(messages2)} messages in phase 2")

        # Store final results
        result_dict["local_temp"] = local_machine.read_variable("local_temp")
        result_dict["success"] = True
        machine_log(f"Final local temperature: {result_dict['local_temp']}")
        machine_log("Exit!")

    except Exception as e:
        machine_log(f"Error: {e}")
        result_dict["error"] = str(e)
        result_dict["success"] = False


def main() -> None:
    # Set up multiprocessing
    multiprocessing.set_start_method("spawn")  # Required for some systems

    # Create queues for inter-process communication
    request_queue: multiprocessing.Queue = multiprocessing.Queue()
    response_queue: multiprocessing.Queue = multiprocessing.Queue()
    result_dict = multiprocessing.Manager().dict()

    print("Starting multiprocess distributed tracing example...")

    # Start remote machine process
    remote_process = multiprocessing.Process(
        target=remote_machine_process,
        args=(
            request_queue,
            response_queue,
        ),
    )
    remote_process.start()

    # Give remote process time to initialize
    time.sleep(0.1)

    # Start local machine process
    local_process = multiprocessing.Process(
        target=local_machine_process,
        args=(
            request_queue,
            response_queue,
            result_dict,
        ),
    )
    local_process.start()

    # Wait for local process to complete
    local_process.join(timeout=10.0)

    # Signal remote process to exit by sending a special message
    request_queue.put({"exit": True})

    # Wait for remote process to complete
    remote_process.join(timeout=5.0)

    # Force terminate if still running
    if remote_process.is_alive():
        print("Force terminating remote process...")
        remote_process.terminate()
        remote_process.join()

    # Check results
    if result_dict.get("success"):
        print("\nDistributed tracing completed successfully!")
        print(f"Final local temperature: {result_dict['local_temp']}")
        print(
            "\nNote: Trace events are displayed by cleanup functions when processes terminate."
        )
    else:
        error_msg = result_dict.get("error", "Unknown error")
        print(f"\nDistributed tracing failed: {error_msg}")

    print("\nMultiprocess example completed.")


if __name__ == "__main__":
    main()
