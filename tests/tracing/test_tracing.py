import json
from pathlib import Path
from typing import Any
import uuid
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode, VariableNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.behavior.local_execution_node import (
    ReadVariableNode,
    WriteVariableNode,
    WaitConditionNode,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.tracing import (
    get_global_collector,
    clear_traces,
    TraceEventType,
    TraceLevel,
    export_traces_json,
    set_global_trace_level,
)


class TestDataModelTracing:
    def test_tracing_disabled_by_default(self) -> None:
        clear_traces()
        _ = DataModel()
        collector = get_global_collector()
        assert collector.level == TraceLevel.NONE
        assert len(collector.events) == 0

    def test_tracing_enabled(self) -> None:
        clear_traces()
        _ = DataModel()
        collector = get_global_collector()
        assert collector.level == TraceLevel.NONE

    def test_tracing_records_changes(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.VARIABLES)
        data_model = DataModel(name="test_dm")
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        data_model.write_variable("test_var", 20.0)

        collector = get_global_collector()
        variable_events = collector.get_events(TraceEventType.VARIABLE_WRITE)
        assert len(variable_events) == 1
        event = variable_events[0]
        assert event.details["variable_id"] == "test_var"
        assert event.details["old_value"] == 10.0
        assert event.details["new_value"] == 20.0
        assert event.details["success"]
        assert event.data_model_id == "test_dm"
        assert isinstance(event.timestamp, float)

    def test_tracing_records_reads(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.VARIABLES)
        data_model = DataModel()
        var = NumericalVariableNode(id="test_var", name="test", value=15.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        value = data_model.read_variable("test_var")

        collector = get_global_collector()
        variable_events = collector.get_events(TraceEventType.VARIABLE_READ)
        assert len(variable_events) == 1
        event = variable_events[0]
        assert event.details["variable_id"] == "test_var"
        assert event.details["value"] == 15.0
        assert value == 15.0
        assert isinstance(event.timestamp, float)

    def test_export_trace(self, tmp_path: Path) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.VARIABLES)
        data_model = DataModel()
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        data_model.write_variable("test_var", 20.0)

        filepath = tmp_path / "trace.json"
        export_traces_json(str(filepath))

        with open(filepath) as f:
            data = json.load(f)

        assert data[0]["event_type"] == "variable_write"
        assert len(data) == 1
        assert data[0]["details"]["variable_id"] == "test_var"
        assert data[0]["details"]["old_value"] == 10.0
        assert data[0]["details"]["new_value"] == 20.0
        assert data[0]["details"]["success"]
        assert "test_var" in data[0]["details"].values()

    def test_tracing_records_method_calls(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.METHODS)
        data_model = DataModel()

        # Create return value node
        return_var = NumericalVariableNode(id="return", name="return", value=0)

        # Create a simple method that returns a value
        def test_callback(x: int = 5) -> int:
            return x * 2

        method = MethodNode(
            id="test_method", name="test", returns=[return_var], callback=test_callback
        )
        data_model.root.add_child(method)
        data_model._register_nodes(data_model.root)

        result = data_model.call_method("test_method")

        collector = get_global_collector()
        method_start_events = collector.get_events(TraceEventType.METHOD_START)
        method_end_events = collector.get_events(TraceEventType.METHOD_END)

        assert len(method_start_events) == 1
        assert len(method_end_events) == 1

        start_event = method_start_events[0]
        end_event = method_end_events[0]

        assert start_event.details["method_id"] == "test_method"
        assert start_event.details["args"] == {}
        assert isinstance(start_event.timestamp, float)

        assert end_event.details["method_id"] == "test_method"
        assert end_event.details["returns"] == {"return": 10}  # x=5 * 2 = 10
        assert isinstance(end_event.details["execution_time"], float)
        assert end_event.details["execution_time"] > 0
        assert isinstance(end_event.timestamp, float)

        # Verify the method actually executed correctly
        assert result.return_values == {"return": 10}

    def test_tracing_records_message_send_and_receive(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.COMMUNICATION)
        data_model = DataModel()

        # Create a simple variable for testing
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Create a mock protocol manager to test message tracing
        from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
            FrostProtocolMng,
        )
        from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
        from machine_data_model.protocols.frost_v1.frost_header import (
            FrostHeader,
            MsgType,
            MsgNamespace,
            VariableMsgName,
        )
        from machine_data_model.protocols.frost_v1.frost_payload import VariablePayload

        protocol_mng = FrostProtocolMng(data_model)

        # Create a read request message
        read_msg = FrostMessage(
            sender="client",
            target="server",
            identifier="test-id",
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(node="test_var"),
        )

        # Handle the request - this should generate MESSAGE_RECEIVE and MESSAGE_SEND events
        response = protocol_mng.handle_request(read_msg)

        collector = get_global_collector()

        # Check MESSAGE_RECEIVE event
        receive_events = collector.get_events(TraceEventType.MESSAGE_RECEIVE)
        assert len(receive_events) == 1
        receive_event = receive_events[0]
        assert receive_event.details["message_type"] == "VARIABLE.READ"
        assert receive_event.details["sender"] == "client"
        assert isinstance(receive_event.timestamp, float)

        # Check MESSAGE_SEND event (response)
        send_events = collector.get_events(TraceEventType.MESSAGE_SEND)
        assert len(send_events) == 1
        send_event = send_events[0]
        assert send_event.details["message_type"] == "VARIABLE.READ"
        assert send_event.details["target"] == "client"
        assert send_event.details["payload"]["value"] == 10.0
        assert isinstance(send_event.timestamp, float)

        # Verify response is correct
        assert response is not None
        assert isinstance(response, FrostMessage)
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.value == 10.0

    def test_tracing_records_wait_conditions(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.COMMUNICATION)
        data_model = DataModel()

        # Create a variable to wait on
        counter_var = NumericalVariableNode(id="counter", name="counter", value=0)
        data_model.root.add_child(counter_var)
        data_model._register_nodes(data_model.root)

        # Create a wait condition that waits for counter >= 5
        wait_condition = WaitConditionNode(
            variable_node="counter",
            rhs=5,
            op=WaitConditionOperator.GE,
        )
        wait_condition.set_ref_node(counter_var)

        # Create a control flow context
        context = ExecutionContext(str(uuid.uuid4()))

        # First execution - condition not met, should start waiting
        result1 = wait_condition.execute(context)
        assert not result1.success  # Should fail because condition not met

        # Check that WAIT_START was recorded
        collector = get_global_collector()
        wait_start_events = collector.get_events(TraceEventType.WAIT_START)
        assert len(wait_start_events) == 1

        start_event = wait_start_events[0]
        assert start_event.details["variable_id"] == "counter"
        assert start_event.details["condition"] == "0 >= 5"  # Full condition string
        assert start_event.details["expected_value"] == 5
        assert isinstance(start_event.timestamp, float)

        # Update the variable to meet the condition
        data_model.write_variable("counter", 7)

        # Execute again - condition met, should stop waiting
        result2 = wait_condition.execute(context)
        assert result2.success  # Should succeed now

        # Check that WAIT_END was recorded
        wait_end_events = collector.get_events(TraceEventType.WAIT_END)
        assert len(wait_end_events) == 1

        end_event = wait_end_events[0]
        assert end_event.details["variable_id"] == "counter"
        assert isinstance(end_event.details["wait_duration"], float)
        assert end_event.details["wait_duration"] > 0
        assert isinstance(end_event.timestamp, float)

    def test_tracing_records_subscriptions(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.COMMUNICATION)
        data_model = DataModel()
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Subscribe to the variable
        var.subscribe(VariableSubscription("subscriber_1"))

        collector = get_global_collector()
        subscribe_events = collector.get_events(TraceEventType.SUBSCRIBE)
        assert len(subscribe_events) == 1
        event = subscribe_events[0]
        assert event.details["variable_id"] == "test_var"
        assert event.details["subscriber_id"] == "subscriber_1"
        assert isinstance(event.timestamp, float)

    def test_tracing_records_unsubscriptions(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.COMMUNICATION)
        data_model = DataModel()
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Subscribe and then unsubscribe
        subscription = VariableSubscription("subscriber_1")
        var.subscribe(subscription)
        var.unsubscribe(subscription)

        collector = get_global_collector()
        unsubscribe_events = collector.get_events(TraceEventType.UNSUBSCRIBE)
        assert len(unsubscribe_events) == 1
        event = unsubscribe_events[0]
        assert event.details["variable_id"] == "test_var"
        assert event.details["subscriber_id"] == "subscriber_1"
        assert isinstance(event.timestamp, float)

    def test_tracing_records_notifications(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.COMMUNICATION)
        data_model = DataModel()
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Subscribe to the variable
        var.subscribe(VariableSubscription("subscriber_1"))
        var.subscribe(VariableSubscription("subscriber_2"))

        # Set up a callback to capture notifications
        notifications: list[tuple[str, Any]] = []

        def test_callback(
            subscription: VariableSubscription,
            _: VariableNode,
            value: Any,
        ) -> None:
            notifications.append((subscription.subscriber_id, value))

        var.set_subscription_callback(test_callback)

        # Write to the variable to trigger notifications
        data_model.write_variable("test_var", 20.0)

        collector = get_global_collector()
        notification_events = collector.get_events(TraceEventType.NOTIFICATION)
        assert len(notification_events) == 2  # One for each subscriber

        # Check first notification
        event1 = notification_events[0]
        assert event1.details["variable_id"] == "test_var"
        assert event1.details["subscriber_id"] in ["subscriber_1", "subscriber_2"]
        assert event1.details["value"] == 20.0
        assert isinstance(event1.timestamp, float)

        # Check second notification
        event2 = notification_events[1]
        assert event2.details["variable_id"] == "test_var"
        assert event2.details["subscriber_id"] in ["subscriber_1", "subscriber_2"]
        assert event2.details["value"] == 20.0
        assert isinstance(event2.timestamp, float)

        # Ensure different subscribers were notified
        assert event1.details["subscriber_id"] != event2.details["subscriber_id"]

        # Verify callbacks were called
        assert len(notifications) == 2
        subscriber_ids = [n[0] for n in notifications]
        assert "subscriber_1" in subscriber_ids
        assert "subscriber_2" in subscriber_ids

    def test_tracing_records_control_flow_steps(self) -> None:
        clear_traces()
        set_global_trace_level(TraceLevel.FULL)
        data_model = DataModel()

        # Create a variable for testing
        var = NumericalVariableNode(id="test_var", name="test_var", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Create a composite method node for the control flow
        composite_method = CompositeMethodNode(
            id="test_control_flow_method", name="Test Control Flow Method"
        )
        data_model.root.add_child(composite_method)
        data_model._register_nodes(data_model.root)

        # Create control flow nodes
        read_node = ReadVariableNode(variable_node="test_var", store_as="read_value")
        read_node.set_ref_node(var)

        write_node = WriteVariableNode(variable_node="test_var", value=20.0)
        write_node.set_ref_node(var)

        # Create control flow with the nodes
        control_flow = ControlFlow(
            [read_node, write_node], composite_method_node=composite_method
        )

        # Create context and execute
        context = ExecutionContext("test_context")
        control_flow.execute(context)

        # Check control flow step events
        collector = get_global_collector()
        control_flow_events = collector.get_events(TraceEventType.CONTROL_FLOW_STEP)
        assert len(control_flow_events) == 2  # One for each node

        # Check first event (read node)
        read_event = control_flow_events[0]
        assert read_event.details["node_id"] == "test_var"
        assert read_event.details["node_type"] == "ReadVariableNode"
        assert read_event.details["execution_result"]
        assert read_event.details["program_counter"] == 0
        assert read_event.source == "test_context"
        assert isinstance(read_event.timestamp, float)

        # Check second event (write node)
        write_event = control_flow_events[1]
        assert write_event.details["node_id"] == "test_var"
        assert write_event.details["node_type"] == "WriteVariableNode"
        assert write_event.details["execution_result"]
        assert write_event.details["program_counter"] == 1
        assert write_event.source == "test_context"
        assert isinstance(write_event.timestamp, float)

        # Verify the control flow executed correctly
        assert context.get_value("read_value") == 10.0
        assert data_model.read_variable("test_var") == 20.0


class TestDataModelReferences:
    """Test data model reference functionality using weak references."""

    def test_node_data_model_reference(self) -> None:
        """Test that nodes correctly reference their containing data model."""
        data_model = DataModel(name="test_dm")
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Node should reference the data model
        assert var.data_model is data_model
        assert var.data_model is not None
        assert var.data_model.name == "test_dm"

    def test_node_without_data_model(self) -> None:
        """Test that nodes without data model registration return None."""
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)

        # Node should not have a data model reference
        assert var.data_model is None

    def test_multiple_data_models(self) -> None:
        """Test that nodes correctly reference their respective data models."""
        dm1 = DataModel(name="dm1")
        dm2 = DataModel(name="dm2")

        var1 = NumericalVariableNode(id="var1", name="var1", value=1.0)
        var2 = NumericalVariableNode(id="var2", name="var2", value=2.0)

        dm1.root.add_child(var1)
        dm2.root.add_child(var2)

        dm1._register_nodes(dm1.root)
        dm2._register_nodes(dm2.root)

        # Each node should reference the correct data model
        assert var1.data_model is dm1
        assert var2.data_model is dm2
        assert var1.data_model is not None
        assert var2.data_model is not None
        assert var1.data_model.name == "dm1"
        assert var2.data_model.name == "dm2"

    def test_nested_nodes_data_model_reference(self) -> None:
        """Test that nested nodes correctly reference their data model."""
        from machine_data_model.nodes.folder_node import FolderNode

        data_model = DataModel(name="nested_dm")
        folder = FolderNode(name="folder")
        var = NumericalVariableNode(id="nested_var", name="nested", value=5.0)

        data_model.root.add_child(folder)
        folder.add_child(var)
        data_model._register_nodes(data_model.root)

        # Both folder and variable should reference the data model
        assert folder.data_model is data_model
        assert var.data_model is data_model
        assert folder.data_model is not None
        assert var.data_model is not None
        assert folder.data_model.name == "nested_dm"
        assert var.data_model.name == "nested_dm"
