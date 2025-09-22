import json
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.tracing import (
    get_global_collector,
    clear_traces,
    TraceEventType,
    TraceLevel,
)
from machine_data_model.tracing.core import export_traces_json


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
            id="test_method", 
            name="test", 
            returns=[return_var],
            callback=test_callback
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
