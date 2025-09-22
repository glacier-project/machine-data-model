import json
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.variable_node import NumericalVariableNode
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
