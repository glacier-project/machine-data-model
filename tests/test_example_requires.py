"""The example in examples/requires keeps loading and behaving as described."""

from pathlib import Path

import pytest

from machine_data_model.behavior.execution_error import ExecutionErrorCode
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    OnUnmet,
)
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import VariableNode

EXAMPLE = Path(__file__).parents[1] / "examples" / "requires" / "requires.yml"


def load(strict: bool = True) -> DataModel:
    return DataModelBuilder(strict_requires=strict).from_string(
        EXAMPLE.read_text()
    )


def method(data_model: DataModel, name: str) -> CompositeMethodNode:
    node = data_model.get_node(f"/plant/{name}")
    assert isinstance(node, CompositeMethodNode)
    return node


def variable(data_model: DataModel, name: str) -> VariableNode:
    node = data_model.get_node(f"/plant/{name}")
    assert isinstance(node, VariableNode)
    return node


def test_the_example_loads_in_strict_mode() -> None:
    load(strict=True)


def test_the_guarded_method_reports_what_it_needs() -> None:
    data_model = load()
    start = method(data_model, "start")

    assert [c.variable for c in start.requires] == ["/plant/mode"]
    assert start.is_executable() is False

    variable(data_model, "mode").write(2)

    assert start.is_executable() is True


def test_fail_mode_fails_at_once_then_works() -> None:
    data_model = load()
    state = variable(data_model, "state")

    result = method(data_model, "start_now")()

    assert result.error is not None
    assert result.error.code is ExecutionErrorCode.PRECONDITION_NOT_MET
    assert state.read() == 0

    variable(data_model, "mode").write(2)
    assert method(data_model, "start_now")().error is None
    assert state.read() == 1


def test_wait_mode_stays_pending_and_resumes_when_the_mode_changes() -> None:
    data_model = load()
    caller = method(data_model, "start_when_ready")
    mode, state = variable(data_model, "mode"), variable(data_model, "state")

    result = caller()
    context_id = result.return_values["@context_id"]
    assert isinstance(context_id, str)
    assert state.read() == 0
    assert len(mode.get_subscriptions()) == 1

    mode.write(2)
    caller.resume_execution(context_id)

    assert state.read() == 1
    assert mode.get_subscriptions() == []


def test_the_timeout_is_a_number_of_seconds() -> None:
    data_model = load()
    caller = method(data_model, "start_when_ready")
    node = caller.cfg.nodes()[0]

    assert isinstance(node, CallMethodNode)
    assert node.timeout == 30.0
    assert node.on_unmet is OnUnmet.WAIT


def test_forgetting_on_unmet_is_caught_in_strict_mode() -> None:
    text = EXAMPLE.read_text().replace('          on_unmet: "fail"\n', "")
    assert text != EXAMPLE.read_text()

    with pytest.raises(ValueError, match="on_unmet"):
        DataModelBuilder(strict_requires=True).from_string(text)


def test_the_example_script_runs(capsys: pytest.CaptureFixture[str]) -> None:
    import runpy

    script = EXAMPLE.with_name("requires.py")

    runpy.run_path(str(script), run_name="__main__")

    output = capsys.readouterr().out
    assert "start.is_executable(): False" in output
    assert "PRECONDITION_NOT_MET" in output
    assert "state = 1" in output
