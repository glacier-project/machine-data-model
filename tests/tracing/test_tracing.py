import json
import uuid
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.behavior.local_execution_node import (
    WaitConditionNode,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow_scope import ControlFlowScope
from machine_data_model.tracing import (
    get_global_collector,
    clear_traces,
    TraceEventType,
    TraceLevel,
    export_traces_json,
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
        _ = DataModel(trace_level=TraceLevel.VARIABLES)
        collector = get_global_collector()
        assert collector.level == TraceLevel.VARIABLES

    def test_tracing_records_changes(self) -> None:
        clear_traces()
        data_model = DataModel(trace_level=TraceLevel.VARIABLES)
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
        assert event.details["success"] == True
        assert isinstance(event.timestamp, float)

    def test_tracing_records_reads(self) -> None:
        clear_traces()
        data_model = DataModel(trace_level=TraceLevel.VARIABLES)
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

    def test_export_trace(self, tmp_path) -> None:
        clear_traces()
        data_model = DataModel(trace_level=TraceLevel.VARIABLES)
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
        assert data[0]["details"]["success"] == True
        assert "test_var" in data[0]["details"].values()

    def test_tracing_records_method_calls(self) -> None:
        clear_traces()
        data_model = DataModel(trace_level=TraceLevel.METHODS)

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
        data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)

        # Create a simple variable for testing
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Create a mock protocol manager to test message tracing
        from machine_data_model.protocols.frost_v1.frost_protocol_mng import FrostProtocolMng
        from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
        from machine_data_model.protocols.frost_v1.frost_header import FrostHeader, MsgType, MsgNamespace, VariableMsgName
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
        data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)

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

        # Create a control flow scope
        scope = ControlFlowScope(str(uuid.uuid4()))

        # First execution - condition not met, should start waiting
        result1 = wait_condition.execute(scope)
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
        result2 = wait_condition.execute(scope)
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
        data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Subscribe to the variable
        var.subscribe("subscriber_1")

        collector = get_global_collector()
        subscribe_events = collector.get_events(TraceEventType.SUBSCRIBE)
        assert len(subscribe_events) == 1
        event = subscribe_events[0]
        assert event.details["variable_id"] == "test_var"
        assert event.details["subscriber_id"] == "subscriber_1"
        assert isinstance(event.timestamp, float)

    def test_tracing_records_unsubscriptions(self) -> None:
        clear_traces()
        data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Subscribe and then unsubscribe
        var.subscribe("subscriber_1")
        var.unsubscribe("subscriber_1")

        collector = get_global_collector()
        unsubscribe_events = collector.get_events(TraceEventType.UNSUBSCRIBE)
        assert len(unsubscribe_events) == 1
        event = unsubscribe_events[0]
        assert event.details["variable_id"] == "test_var"
        assert event.details["subscriber_id"] == "subscriber_1"
        assert isinstance(event.timestamp, float)

    def test_tracing_records_notifications(self) -> None:
        clear_traces()
        data_model = DataModel(trace_level=TraceLevel.COMMUNICATION)
        var = NumericalVariableNode(id="test_var", name="test", value=10.0)
        data_model.root.add_child(var)
        data_model._register_nodes(data_model.root)

        # Subscribe to the variable
        var.subscribe("subscriber_1")
        var.subscribe("subscriber_2")

        # Set up a callback to capture notifications
        notifications = []
        def test_callback(subscriber_id, variable_node, value):
            notifications.append((subscriber_id, value))

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
